import logging
import os
import time
from io import BytesIO

import httpx
from fastapi import HTTPException

from ..tracing import Span

logger = logging.getLogger(__name__)

URL = "http://libreoffice:8000/convert"


def is_available() -> bool:
    return os.environ.get("LIBREOFFICE_ENABLED", "true").lower() == "true"


async def convert(file_bytes: bytes, mime_type: str, filename: str, target_format: str, timeout: float, parent: Span | None = None) -> tuple[bytes, str]:
    """Convert a file via headless LibreOffice. Returns (converted_bytes, new_mime_type)."""
    content = BytesIO(file_bytes)

    async with httpx.AsyncClient(timeout=timeout) as client:
        http_span = None
        if parent is not None:
            http_span = Span(name="http_request", attributes={"input_size_bytes": len(file_bytes), "target_format": target_format})
            http_span._start = time.monotonic()
            parent.children.append(http_span)

        try:
            response = await client.post(
                URL,
                files=[("file", (filename, content, mime_type))],
                params={"format": target_format},
            )
        except httpx.TimeoutException:
            if http_span:
                http_span._end = time.monotonic()
                http_span.set(error="timeout")
            raise HTTPException(status_code=504, detail="LibreOffice service timeout")
        except httpx.RequestError as e:
            if http_span:
                http_span._end = time.monotonic()
                http_span.set(error=str(e))
            raise HTTPException(status_code=502, detail=f"Failed to reach LibreOffice: {e}")

        if http_span:
            http_span._end = time.monotonic()
            http_span.set(output_size_bytes=len(response.content), status_code=response.status_code)

    if response.status_code != 200:
        raise HTTPException(
            status_code=502,
            detail=f"LibreOffice service error {response.status_code}: {response.text}",
        )

    FORMAT_MIMES = {
        "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
        "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "pdf": "application/pdf",
    }
    converted_mime = FORMAT_MIMES.get(target_format, "application/octet-stream")

    return response.content, converted_mime
