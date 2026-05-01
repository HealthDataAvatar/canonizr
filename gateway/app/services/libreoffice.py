import logging
import os
import time
from io import BytesIO

import httpx

from .retry import request_with_retry
from ..tracing import Span

logger = logging.getLogger(__name__)

URL = "http://libreoffice:8000/convert"


def is_available() -> bool:
    return os.environ.get("LIBREOFFICE_ENABLED", "true").lower() == "true"


async def convert(file_bytes: bytes, mime_type: str, filename: str, target_format: str, deadline: float, parent: Span | None = None) -> tuple[bytes, str]:
    """Convert a file via headless LibreOffice. Returns (converted_bytes, new_mime_type)."""
    content = BytesIO(file_bytes)

    http_span = None
    if parent is not None:
        http_span = Span(name="http_request", attributes={"input_size_bytes": len(file_bytes), "target_format": target_format})
        http_span._start = time.monotonic()
        parent.children.append(http_span)

    async with httpx.AsyncClient() as client:
        response = await request_with_retry(
            client, "POST", URL,
            deadline=deadline,
            service_name="libreoffice",
            span=http_span,
            files=[("file", (filename, content, mime_type))],
            params={"format": target_format},
        )

    if http_span:
        http_span._end = time.monotonic()

    FORMAT_MIMES = {
        "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
        "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "pdf": "application/pdf",
    }
    converted_mime = FORMAT_MIMES.get(target_format, "application/octet-stream")

    return response.content, converted_mime
