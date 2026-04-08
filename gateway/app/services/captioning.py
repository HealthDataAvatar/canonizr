import base64
import logging
import os
import time

import httpx

from ..imageconv import to_png
from ..prompts import CAPTION, TRANSCRIBE
from ..response import ConvertResult

logger = logging.getLogger(__name__)

ENDPOINT = "http://captioning:8080/v1/chat/completions"


def is_available() -> bool:
    return os.environ.get("CAPTIONING_ENABLED", "true").lower() == "true"


async def _call(image_b64: str, mime_type: str, prompt: str, max_tokens: int, timeout: float) -> tuple[dict, float]:
    """Send a base64-encoded image to the captioning service."""
    payload = {
        "messages": [
            {
                "role": "user",
                "content": [
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:{mime_type};base64,{image_b64}",
                        },
                    },
                    {
                        "type": "text",
                        "text": prompt,
                    },
                ],
            }
        ],
        "max_tokens": max_tokens,
    }

    async with httpx.AsyncClient(timeout=timeout) as client:
        start_time = time.time()
        response = await client.post(ENDPOINT, json=payload)
        elapsed = (time.time() - start_time) * 1000

        if response.status_code != 200:
            raise httpx.HTTPStatusError(
                f"Captioning service error {response.status_code}: {response.text}",
                request=response.request,
                response=response,
            )

        return response.json(), elapsed


def _extract_content(raw: dict) -> str:
    return raw.get("choices", [{}])[0].get("message", {}).get("content", "")


async def caption_text(image_b64: str, mime_type: str, timeout: float) -> str:
    """Generate an alt-text caption. Returns just the string."""
    raw, _ = await _call(image_b64, mime_type, CAPTION, max_tokens=300, timeout=timeout)
    return _extract_content(raw)


async def caption(image_bytes: bytes, mime_type: str, timeout: float) -> ConvertResult:
    """Caption a standalone image upload."""
    image_bytes, mime_type = to_png(image_bytes, mime_type)
    image_b64 = base64.b64encode(image_bytes).decode("utf-8")
    raw, elapsed = await _call(image_b64, mime_type, CAPTION, max_tokens=300, timeout=timeout)
    return ConvertResult(
        markdown=_extract_content(raw),
        detected_type=mime_type,
        actions=["captioning"],
        processing_time_ms=elapsed,
        images_captioned=1,
    )


async def transcribe(image_bytes: bytes, mime_type: str, timeout: float) -> ConvertResult:
    """Transcribe an image of text, table, or handwriting."""
    image_bytes, mime_type = to_png(image_bytes, mime_type)
    image_b64 = base64.b64encode(image_bytes).decode("utf-8")
    raw, elapsed = await _call(image_b64, mime_type, TRANSCRIBE, max_tokens=1024, timeout=timeout)
    return ConvertResult(
        markdown=_extract_content(raw),
        detected_type=mime_type,
        actions=["transcription"],
        processing_time_ms=elapsed,
    )
