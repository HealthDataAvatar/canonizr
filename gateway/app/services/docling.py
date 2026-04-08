import logging
import re
import time
from enum import Enum
from io import BytesIO

import httpx
from fastapi import HTTPException

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


def _get_captionable_images(json_content: dict) -> dict[str, dict]:
    """Filter Docling JSON for non-decorative images worth captioning."""
    pictures = json_content.get("pictures", [])
    captionable = {}

    for pic in pictures:
        image = pic.get("image")
        if not image or not image.get("uri"):
            continue

        size = image.get("size", {})
        width = size.get("width", 0)
        height = size.get("height", 0)

        if width < MIN_IMAGE_DIMENSION or height < MIN_IMAGE_DIMENSION:
            logger.info("Skipping small image (%dx%d)", width, height)
            continue

        classifications = {
            a.get("label") for a in pic.get("annotations", [])
            if a.get("label")
        }
        if classifications & {label.value for label in SKIP_LABELS}:
            logger.info("Skipping decorative image (labels: %s)", classifications)
            continue

        captionable[image["uri"]] = {
            "mime_type": image.get("mimetype", "image/png"),
            "width": width,
            "height": height,
        }

    return captionable


async def _caption_images(md_content: str, captionable: dict[str, dict], timeout: float) -> tuple[str, int, int]:
    """Replace base64 images in markdown with captions. Returns (markdown, captioned, skipped)."""
    matches = list(IMAGE_RE.finditer(md_content))
    if not matches:
        return md_content, 0, 0

    captioned = 0
    skipped = 0
    result = md_content

    for match in reversed(matches):
        alt_text = match.group(1)
        mime_type = match.group(2)
        image_b64 = match.group(3)
        data_uri = f"data:{mime_type};base64,{image_b64}"

        if data_uri not in captionable:
            skipped += 1
            result = result[:match.start()] + result[match.end():]
            continue

        try:
            caption_text = await captioning.caption_text(image_b64, mime_type, timeout)
            replacement = f"![{caption_text}]"
            captioned += 1
        except Exception:
            logger.warning("Captioning failed for image, using fallback")
            replacement = f"![{alt_text or 'Image'}]"

        result = result[:match.start()] + replacement + result[match.end():]

    return result, captioned, skipped


async def convert(file_bytes: bytes, mime_type: str, timeout: float) -> ConvertResult:
    """Extract a PDF via Docling, then caption non-decorative figures."""
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

    if response.status_code != 200:
        raise HTTPException(
            status_code=502,
            detail=f"Docling service error {response.status_code}: {response.text}",
        )

    raw = response.json()
    md_content = raw.get("document", {}).get("md_content", "")
    json_content = raw.get("document", {}).get("json_content", {})

    actions = ["docling"]
    images_captioned = 0
    images_skipped = 0

    if captioning.is_available():
        captionable = _get_captionable_images(json_content)
        md_content, images_captioned, images_skipped = await _caption_images(
            md_content, captionable, timeout
        )
        if images_captioned or images_skipped:
            actions.append(f"captioning ({images_captioned} captioned, {images_skipped} skipped)")

    elapsed = (time.time() - start_time) * 1000

    return ConvertResult(
        markdown=md_content,
        detected_type=mime_type,
        actions=actions,
        processing_time_ms=elapsed,
        images_captioned=images_captioned,
        images_skipped=images_skipped,
    )
