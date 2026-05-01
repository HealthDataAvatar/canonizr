import logging
import os
import time
from io import BytesIO

import httpx

from . import captioning
from .image_postprocess import CaptionResult, IMAGE_RE, caption_images, label_images
from .retry import request_with_retry
from ..response import ConvertResult
from ..tracing import Span

logger = logging.getLogger(__name__)

URL = os.environ.get("DOCLING_ENDPOINT") or "http://docling:5001/v1/convert/file"


async def convert(file_bytes: bytes, mime_type: str, deadline: float, parent: Span | None = None) -> ConvertResult:
    """Extract a PDF via Docling, then caption non-decorative figures."""
    content = BytesIO(file_bytes)

    http_span = None
    if parent is not None:
        http_span = Span(name="http_request", attributes={"input_size_bytes": len(file_bytes)})
        http_span._start = time.monotonic()
        parent.children.append(http_span)

    async with httpx.AsyncClient() as client:
        response = await request_with_retry(
            client, "POST", URL,
            deadline=deadline,
            service_name="docling",
            span=http_span,
            files=[("files", ("document.pdf", content, mime_type))],
            data={
                "to_formats": ["md", "json"],
                "image_export_mode": "embedded",
                "do_ocr": False,
            },
        )

    if http_span:
        http_span._end = time.monotonic()

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
            cap = await caption_images(md_content, pictures, deadline, parent)
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
