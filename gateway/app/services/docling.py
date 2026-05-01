import logging
import os
import time
from io import BytesIO

import httpx
from fastapi import HTTPException

from . import captioning
from .image_postprocess import CaptionResult, ImageOutcome, IMAGE_RE, caption_images
from ..response import ConvertResult

logger = logging.getLogger(__name__)

URL = os.environ.get("DOCLING_ENDPOINT") or "http://docling:5001/v1/convert/file"


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
    cap = CaptionResult(markdown=md_content)

    image_count = len(list(IMAGE_RE.finditer(md_content)))

    if captioning.is_available() and image_count > 0:
        cap = await caption_images(md_content, pictures, timeout, debug)
        actions.append("captioning")
        if cap.failed:
            failed_details = [d for d in debug[-1].get("images", []) if d.get("outcome") == ImageOutcome.FAILED_UPSTREAM.value]
            reason = failed_details[0].get("error", "unknown error") if failed_details else "unknown error"
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

    elapsed = (time.time() - start_time) * 1000

    return ConvertResult(
        markdown=cap.markdown,
        detected_type=mime_type,
        actions=actions,
        warnings=warnings,
        completeness="partial" if warnings else "full",
        processing_time_ms=elapsed,
        images_captioned=cap.captioned,
        images_skipped=cap.skipped,
        images_errored=cap.errored,
        images_failed=cap.failed,
        debug=debug,
    )
