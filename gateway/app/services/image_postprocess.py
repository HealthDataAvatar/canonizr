import asyncio
import base64
import logging
import os
import re
from dataclasses import dataclass
from enum import Enum
from io import BytesIO

from PIL import Image

from . import captioning

logger = logging.getLogger(__name__)

MIN_IMAGE_DIMENSION = 50
CAPTIONING_CONCURRENCY = int(os.environ.get("CAPTIONING_CONCURRENCY", "4"))

IMAGE_RE = re.compile(r"!\[([^\]]*)\]\(data:(image/[^;]+);base64,([^)]+)\)")


class PictureClassification(str, Enum):
    """Docling picture classification labels."""
    PIE_CHART = "pie_chart"
    BAR_CHART = "bar_chart"
    STACKED_BAR_CHART = "stacked_bar_chart"
    LINE_CHART = "line_chart"
    SCATTER_CHART = "scatter_chart"
    HEATMAP = "heatmap"
    STRATIGRAPHIC_CHART = "stratigraphic_chart"
    FLOW_CHART = "flow_chart"
    ELECTRICAL_DIAGRAM = "electrical_diagram"
    CAD_DRAWING = "cad_drawing"
    NATURAL_IMAGE = "natural_image"
    SCREENSHOT = "screenshot"
    MAP = "map"
    REMOTE_SENSING = "remote_sensing"
    PICTURE_GROUP = "picture_group"
    CHEMISTRY_MOLECULAR = "chemistry_molecular_structure"
    CHEMISTRY_MARKUSH = "chemistry_markush_structure"
    LOGO = "logo"
    ICON = "icon"
    SIGNATURE = "signature"
    STAMP = "stamp"
    QR_CODE = "qr_code"
    BAR_CODE = "bar_code"
    OTHER = "other"


SKIP_LABELS = {
    PictureClassification.LOGO,
    PictureClassification.ICON,
    PictureClassification.SIGNATURE,
    PictureClassification.STAMP,
    PictureClassification.QR_CODE,
    PictureClassification.BAR_CODE,
}

SKIP_LABEL_VALUES = {label.value for label in SKIP_LABELS}


class CaptioningUpstreamError(Exception):
    """Raised when the captioning service fails for an image."""
    def __init__(self, index: int, cause: Exception):
        self.index = index
        self.cause = cause
        super().__init__(f"Captioning failed for image at index {index}: {cause}")


def _get_skip_indices(pictures: list[dict]) -> set[int]:
    """Return indices of pictures that should be skipped based on classification labels."""
    skip = set()
    for i, pic in enumerate(pictures):
        labels = {a.get("label") for a in pic.get("annotations", []) if a.get("label")}
        if labels & SKIP_LABEL_VALUES:
            logger.info("Skipping decorative image at index %d (labels: %s)", i, labels)
            skip.add(i)
    return skip


def _image_dimensions(image_b64: str) -> tuple[int, int]:
    """Decode a base64 image and return (width, height)."""
    img = Image.open(BytesIO(base64.b64decode(image_b64)))
    return img.size


def _get_label(pictures: list[dict], index: int) -> str:
    """Get the first classification label for a picture, title-cased."""
    labels = {a.get("label") for a in pictures[index].get("annotations", []) if a.get("label")}
    label = next(iter(labels), "Image")
    return label.replace("_", " ").title()


class ImageOutcome(str, Enum):
    """Outcome of processing a single image in the pipeline."""
    CAPTIONED = "captioned"
    SKIPPED_DECORATIVE = "skipped_decorative"
    SKIPPED_TOO_SMALL = "skipped_too_small"
    ERRORED_DECODE = "errored_decode"
    LABELLED = "labelled"
    NEEDS_CAPTION = "needs_caption"


@dataclass
class CaptionResult:
    markdown: str
    captioned: int = 0
    skipped: int = 0
    errored: int = 0
    labelled: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0


def _classify_images(md_content: str, pictures: list[dict]) -> list[dict]:
    """Classify each embedded image. Returns a list of entries in forward order.

    Each entry has: index, match, mime_type, image_b64, and either an outcome
    with replacement, or outcome=NEEDS_CAPTION for content images."""
    matches = list(IMAGE_RE.finditer(md_content))
    skip_indices = _get_skip_indices(pictures)
    entries = []

    for index, match in enumerate(matches):
        mime_type = match.group(2)
        image_b64 = match.group(3)
        entry: dict = {"index": index, "match": match, "mime_type": mime_type, "image_b64": image_b64}

        if index in skip_indices:
            entry["replacement"] = f"![{_get_label(pictures, index)}]"
            entry["outcome"] = ImageOutcome.SKIPPED_DECORATIVE
        else:
            try:
                width, height = _image_dimensions(image_b64)
            except Exception:
                logger.warning("Could not decode image at index %d", index)
                entry["replacement"] = "![Image corrupted]"
                entry["outcome"] = ImageOutcome.ERRORED_DECODE
            else:
                entry["dimensions"] = [width, height]
                if width < MIN_IMAGE_DIMENSION or height < MIN_IMAGE_DIMENSION:
                    entry["outcome"] = ImageOutcome.SKIPPED_TOO_SMALL
                else:
                    entry["outcome"] = ImageOutcome.NEEDS_CAPTION

        entries.append(entry)

    return entries


def _apply_replacements(md_content: str, entries: list[dict]) -> tuple[str, dict[ImageOutcome, int], list[dict]]:
    """Apply replacements in reverse order. Returns (result_markdown, counts, image_details)."""
    counts: dict[ImageOutcome, int] = {o: 0 for o in ImageOutcome}
    image_details = []
    result = md_content

    for entry in reversed(entries):
        match = entry["match"]
        replacement = entry.get("replacement")
        outcome = entry["outcome"]

        if replacement is None:
            result = result[:match.start()] + result[match.end():]
        else:
            result = result[:match.start()] + replacement + result[match.end():]

        counts[outcome] += 1
        detail: dict = {"index": entry["index"], "outcome": outcome.value}
        if "dimensions" in entry:
            detail["dimensions"] = entry["dimensions"]
        image_details.append(detail)

    return result, counts, image_details


async def caption_images(
    md_content: str, pictures: list[dict], timeout: float, debug: list[dict],
) -> CaptionResult:
    """Replace base64 images in markdown with captions. Raises CaptioningUpstreamError on failure."""
    entries = _classify_images(md_content, pictures)
    if not entries:
        return CaptionResult(markdown=md_content)

    semaphore = asyncio.Semaphore(CAPTIONING_CONCURRENCY)
    tasks: list[tuple[int, asyncio.Task]] = []

    async def _caption_one(image_b64: str, mime_type: str):
        async with semaphore:
            return await captioning.caption_text(image_b64, mime_type, timeout)

    for entry in entries:
        if entry["outcome"] == ImageOutcome.NEEDS_CAPTION:
            task = asyncio.create_task(_caption_one(entry["image_b64"], entry["mime_type"]))
            tasks.append((entry["index"], task))

    total_prompt_tokens = 0
    total_completion_tokens = 0

    for index, task in tasks:
        entry = entries[index]
        try:
            result = await task
            entry["replacement"] = f"![{result.text}]"
            entry["outcome"] = ImageOutcome.CAPTIONED
            total_prompt_tokens += result.prompt_tokens
            total_completion_tokens += result.completion_tokens
        except Exception as e:
            for _, remaining in tasks:
                remaining.cancel()
            raise CaptioningUpstreamError(index, e) from e

    result, counts, image_details = _apply_replacements(md_content, entries)

    debug.append({
        "step": "captioning",
        "md_image_count": len(entries),
        "captioned": counts[ImageOutcome.CAPTIONED],
        "skipped": counts[ImageOutcome.SKIPPED_DECORATIVE] + counts[ImageOutcome.SKIPPED_TOO_SMALL],
        "prompt_tokens": total_prompt_tokens,
        "completion_tokens": total_completion_tokens,
        "images": image_details,
    })

    return CaptionResult(
        markdown=result,
        captioned=counts[ImageOutcome.CAPTIONED],
        skipped=counts[ImageOutcome.SKIPPED_DECORATIVE] + counts[ImageOutcome.SKIPPED_TOO_SMALL],
        errored=counts[ImageOutcome.ERRORED_DECODE],
        prompt_tokens=total_prompt_tokens,
        completion_tokens=total_completion_tokens,
    )


def label_images(md_content: str, pictures: list[dict]) -> CaptionResult:
    """Label images with Docling classifications, preserving base64 for content images."""
    entries = _classify_images(md_content, pictures)
    if not entries:
        return CaptionResult(markdown=md_content)

    for entry in entries:
        if entry["outcome"] == ImageOutcome.NEEDS_CAPTION:
            label = _get_label(pictures, entry["index"])
            entry["replacement"] = f"![{label}](data:{entry['mime_type']};base64,{entry['image_b64']})"
            entry["outcome"] = ImageOutcome.LABELLED

    result, counts, _ = _apply_replacements(md_content, entries)

    return CaptionResult(
        markdown=result,
        skipped=counts[ImageOutcome.SKIPPED_DECORATIVE] + counts[ImageOutcome.SKIPPED_TOO_SMALL],
        errored=counts[ImageOutcome.ERRORED_DECODE],
        labelled=counts[ImageOutcome.LABELLED],
    )
