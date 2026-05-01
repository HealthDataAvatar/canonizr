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


class ImageOutcome(str, Enum):
    """Outcome of processing a single image in the pipeline."""
    CAPTIONED = "captioned"
    SKIPPED_DECORATIVE = "skipped_decorative"
    SKIPPED_TOO_SMALL = "skipped_too_small"
    ERRORED_DECODE = "errored_decode"
    FAILED_UPSTREAM = "failed_upstream"


@dataclass
class CaptionResult:
    markdown: str
    captioned: int = 0
    skipped: int = 0
    errored: int = 0
    failed: int = 0



async def caption_images(
    md_content: str, pictures: list[dict], timeout: float, debug: list[dict],
) -> CaptionResult:
    """Replace base64 images in markdown with captions."""
    matches = list(IMAGE_RE.finditer(md_content))
    if not matches:
        return CaptionResult(markdown=md_content)

    skip_indices = _get_skip_indices(pictures)
    semaphore = asyncio.Semaphore(CAPTIONING_CONCURRENCY)

    # First pass: classify each image and collect captioning tasks
    per_image: list[dict] = []  # one entry per match, in forward order
    tasks: list[tuple[int, asyncio.Task]] = []

    async def _caption_one(image_b64: str, mime_type: str) -> str:
        async with semaphore:
            return await captioning.caption_text(image_b64, mime_type, timeout)

    for index, match in enumerate(matches):
        alt_text = match.group(1)
        mime_type = match.group(2)
        image_b64 = match.group(3)
        entry: dict = {"index": index, "alt_text": alt_text, "match": match}

        if index in skip_indices:
            labels = {a.get("label") for a in pictures[index].get("annotations", []) if a.get("label")}
            label = next(iter(labels), "Image")
            entry["replacement"] = f"![{label.replace('_', ' ').title()}]"
            entry["outcome"] = ImageOutcome.SKIPPED_DECORATIVE
            entry["label"] = label
        else:
            try:
                width, height = _image_dimensions(image_b64)
            except Exception:
                logger.warning("Could not decode image at index %d", index)
                entry["outcome"] = ImageOutcome.ERRORED_DECODE
            else:
                entry["dimensions"] = [width, height]
                if width < MIN_IMAGE_DIMENSION or height < MIN_IMAGE_DIMENSION:
                    entry["outcome"] = ImageOutcome.SKIPPED_TOO_SMALL
                else:
                    task = asyncio.create_task(_caption_one(image_b64, mime_type))
                    tasks.append((index, task))

        per_image.append(entry)

    # Await all captioning calls concurrently
    for index, task in tasks:
        entry = per_image[index]
        try:
            text = await task
            entry["replacement"] = f"![{text}]"
            entry["outcome"] = ImageOutcome.CAPTIONED
        except Exception as e:
            logger.warning("Captioning failed for image at index %d: %s", index, e)
            entry["replacement"] = f"![{entry['alt_text'] or 'Image'}]"
            entry["outcome"] = ImageOutcome.FAILED_UPSTREAM
            entry["error"] = str(e)

    # Second pass: apply replacements in reverse order to preserve offsets
    counts: dict[ImageOutcome, int] = {o: 0 for o in ImageOutcome}
    image_details = []
    result = md_content

    for entry in reversed(per_image):
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
        if "label" in entry:
            detail["label"] = entry["label"]
        if "error" in entry:
            detail["error"] = entry["error"]
        image_details.append(detail)

    debug.append({
        "step": "captioning",
        "md_image_count": len(matches),
        "captioned": counts[ImageOutcome.CAPTIONED],
        "skipped": counts[ImageOutcome.SKIPPED_DECORATIVE] + counts[ImageOutcome.SKIPPED_TOO_SMALL],
        "images": image_details,
    })

    return CaptionResult(
        markdown=result,
        captioned=counts[ImageOutcome.CAPTIONED],
        skipped=counts[ImageOutcome.SKIPPED_DECORATIVE] + counts[ImageOutcome.SKIPPED_TOO_SMALL],
        errored=counts[ImageOutcome.ERRORED_DECODE],
        failed=counts[ImageOutcome.FAILED_UPSTREAM],
    )
