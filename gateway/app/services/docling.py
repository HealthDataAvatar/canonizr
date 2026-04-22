import base64
import logging
import re
import time
from dataclasses import dataclass
from enum import Enum
from io import BytesIO

import httpx
from fastapi import HTTPException
from PIL import Image

from . import captioning
from ..response import ConvertResult

logger = logging.getLogger(__name__)

URL = "http://docling:5001/v1/convert/file"

MIN_IMAGE_DIMENSION = 50

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


@dataclass
class CaptionResult:
    markdown: str
    captioned: int = 0
    skipped: int = 0
    failed: int = 0


async def _caption_images(
    md_content: str, pictures: list[dict], timeout: float, debug: list[dict],
) -> CaptionResult:
    """Replace base64 images in markdown with captions."""
    matches = list(IMAGE_RE.finditer(md_content))
    if not matches:
        return CaptionResult(markdown=md_content)

    skip_indices = _get_skip_indices(pictures)

    captioned = 0
    skipped = 0
    failed = 0
    result = md_content
    image_details = []

    for i, match in enumerate(reversed(matches)):
        index = len(matches) - 1 - i  # original forward index
        alt_text = match.group(1)
        mime_type = match.group(2)
        image_b64 = match.group(3)

        # Use classification label as caption for decorative images
        if index in skip_indices:
            labels = {a.get("label") for a in pictures[index].get("annotations", []) if a.get("label")}
            label = next(iter(labels), "Image")
            replacement = f"![{label.replace('_', ' ').title()}]"
            result = result[:match.start()] + replacement + result[match.end():]
            skipped += 1
            image_details.append({"index": index, "action": "label_from_classification", "label": label})
            continue

        # Check dimensions from actual image bytes
        try:
            width, height = _image_dimensions(image_b64)
        except Exception:
            logger.warning("Could not decode image at index %d", index)
            skipped += 1
            result = result[:match.start()] + result[match.end():]
            image_details.append({"index": index, "action": "skipped_decode_error"})
            continue

        if width < MIN_IMAGE_DIMENSION or height < MIN_IMAGE_DIMENSION:
            skipped += 1
            result = result[:match.start()] + result[match.end():]
            image_details.append({"index": index, "dimensions": [width, height], "action": "skipped_too_small"})
            continue

        # Caption the image
        try:
            caption_text = await captioning.caption_text(image_b64, mime_type, timeout)
            replacement = f"![{caption_text}]"
            captioned += 1
            image_details.append({"index": index, "dimensions": [width, height], "action": "captioned"})
        except Exception as e:
            logger.warning("Captioning failed for image at index %d: %s", index, e)
            replacement = f"![{alt_text or 'Image'}]"
            failed += 1
            image_details.append({"index": index, "dimensions": [width, height], "action": "fallback", "error": str(e)})

        result = result[:match.start()] + replacement + result[match.end():]

    debug.append({
        "step": "captioning",
        "md_image_count": len(matches),
        "captioned": captioned,
        "skipped": skipped,
        "images": image_details,
    })

    return CaptionResult(markdown=result, captioned=captioned, skipped=skipped, failed=failed)


async def convert(file_bytes: bytes, mime_type: str, timeout: float, debug: list[dict] | None = None) -> ConvertResult:
    """Extract a PDF via Docling, then caption non-decorative figures."""
    if debug is None:
        debug = []
    content = BytesIO(file_bytes)
    start_time = time.time()

    async with httpx.AsyncClient(timeout=timeout) as client:
        try:
            response = await client.post(
                URL,
                files=[("files", ("document.pdf", content, mime_type))],
                data={
                    "to_formats": ["md", "json"],
                    "image_export_mode": "embedded",
                    "do_ocr": False,
                },
            )
        except httpx.TimeoutException:
            raise HTTPException(status_code=504, detail="Docling service timeout")
        except httpx.RequestError as e:
            raise HTTPException(status_code=502, detail=f"Failed to reach Docling: {e}")

    docling_elapsed = (time.time() - start_time) * 1000

    if response.status_code != 200:
        raise HTTPException(
            status_code=502,
            detail=f"Docling service error {response.status_code}: {response.text}",
        )

    raw = response.json()
    md_content = raw.get("document", {}).get("md_content", "")
    json_content = raw.get("document", {}).get("json_content", {})
    pictures = json_content.get("pictures", [])

    debug.append({
        "step": "docling",
        "elapsed_ms": docling_elapsed,
        "md_length": len(md_content),
        "pictures_in_json": len(pictures),
    })

    actions = ["docling"]
    warnings: list[dict] = []
    images_captioned = 0
    images_skipped = 0

    image_count = len(list(IMAGE_RE.finditer(md_content)))

    if captioning.is_available() and image_count > 0:
        cap = await _caption_images(md_content, pictures, timeout, debug)
        md_content = cap.markdown
        images_captioned = cap.captioned
        images_skipped = cap.skipped
        parts = []
        if cap.captioned:
            parts.append(f"{cap.captioned} captioned")
        if cap.skipped:
            parts.append(f"{cap.skipped} skipped")
        if cap.failed:
            parts.append(f"{cap.failed} failed")
        actions.append(f"captioning ({', '.join(parts)})")
        if cap.failed:
            # Extract error from first failed image for the warning message
            errors = [d.get("error", "") for d in debug[-1].get("images", []) if d.get("action") == "fallback"]
            reason = errors[0] if errors else "unknown error"
            warnings.append({
                "code": "captioning_failed",
                "message": f"{cap.failed} image(s) could not be captioned: {reason}",
                "count": cap.failed,
                "config": captioning.get_config(),
            })
    elif image_count > 0:
        warnings.append({
            "code": "captioning_unavailable",
            "message": f"{image_count} image(s) have no descriptions (captioning not available)",
            "count": image_count,
            "config": captioning.get_config(),
        })

    completeness = "partial" if warnings else "full"
    elapsed = (time.time() - start_time) * 1000

    return ConvertResult(
        markdown=md_content,
        detected_type=mime_type,
        actions=actions,
        warnings=warnings,
        completeness=completeness,
        processing_time_ms=elapsed,
        images_captioned=images_captioned,
        images_skipped=images_skipped,
        debug=debug,
    )
