import logging
import os
import time
from io import BytesIO

import httpx
from fastapi import HTTPException

logger = logging.getLogger(__name__)

URL = "http://libreoffice:8000/convert"


def is_available() -> bool:
    return os.environ.get("LIBREOFFICE_ENABLED", "true").lower() == "true"


async def convert(file_bytes: bytes, mime_type: str, filename: str, target_format: str, timeout: float, debug: list[dict] | None = None) -> tuple[bytes, str]:
    """Convert a file via headless LibreOffice. Returns (converted_bytes, new_mime_type)."""
    if debug is None:
        debug = []
    content = BytesIO(file_bytes)
    start_time = time.time()

    async with httpx.AsyncClient(timeout=timeout) as client:
        try:
            response = await client.post(
                URL,
                files=[("file", (filename, content, mime_type))],
                params={"format": target_format},
            )
        except httpx.TimeoutException:
            raise HTTPException(status_code=504, detail="LibreOffice service timeout")
        except httpx.RequestError as e:
            raise HTTPException(status_code=502, detail=f"Failed to reach LibreOffice: {e}")

    elapsed = (time.time() - start_time) * 1000

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

    debug.append({
        "step": "libreoffice",
        "elapsed_ms": elapsed,
        "input_size_bytes": len(file_bytes),
        "output_size_bytes": len(response.content),
        "target_format": target_format,
    })

    return response.content, converted_mime
