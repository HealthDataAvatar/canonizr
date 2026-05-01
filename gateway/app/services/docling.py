import logging
import os
import time
from io import BytesIO

import httpx
from fastapi import HTTPException

from . import captioning
from .image_postprocess import CaptionResult, IMAGE_RE, caption_images, label_images
from ..response import ConvertResult
from ..tracing import Span

logger = logging.getLogger(__name__)

URL = os.environ.get("DOCLING_ENDPOINT") or "http://docling:5001/v1/convert/file"


async def convert(file_bytes: bytes, mime_type: str, timeout: float, parent: Span | None = None) -> ConvertResult:
    """Extract a PDF via Docling, then caption non-decorative figures."""
    content = BytesIO(file_bytes)

    http_span = None
    if parent is not None:
        http_span = Span(name="http_request", attributes={"input_size_bytes": len(file_bytes)})
        http_span._start = time.monotonic()
        parent.children.append(http_span)

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
            if http_span:
                http_span._end = time.monotonic()
                http_span.set(error="timeout")
            raise HTTPException(status_code=504, detail="Docling service timeout")
        except httpx.RequestError as e:
            if http_span:
                http_span._end = time.monotonic()
                http_span.set(error=str(e))
            raise HTTPException(status_code=502, detail=f"Failed to reach Docling: {e}")

    if http_span:
        http_span._end = time.monotonic()
        http_span.set(response_bytes=len(response.content), status_code=response.status_code)

    if response.status_code != 200:
        raise HTTPException(
            status_code=502,
            detail=f"Docling service error {response.status_code}: {response.text}",
        )

    raw = response.json()
    md_content = raw.get("document", {}).get("md_content", "")
    json_content = raw.get("document", {}).get("json_content", {})
    pictures = json_content.get("pictures", [])

    if parent:
        parent.set(md_length=len(md_content), pictures_count=len(pictures))

    actions = ["docling"]
    cap = CaptionResult(markdown=md_content)
    image_count = len(list(IMAGE_RE.finditer(md_content)))

    if image_count > 0:
        if captioning.is_available():
            cap = await caption_images(md_content, pictures, timeout, parent)
            actions.append("captioning")
        else:
            cap = label_images(md_content, pictures)
            actions.append("labelling")

    return ConvertResult(
        markdown=cap.markdown,
        detected_type=mime_type,
        actions=actions,
        images_captioned=cap.captioned,
        images_skipped=cap.skipped,
        images_errored=cap.errored,
        captioning_prompt_tokens=cap.prompt_tokens,
        captioning_completion_tokens=cap.completion_tokens,
    )
