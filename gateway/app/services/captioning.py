import base64
import logging
import os
import time

import httpx
from fastapi import HTTPException

from ..imageconv import to_png
from ..prompts import CAPTION, TRANSCRIBE
from ..response import ConvertResult

logger = logging.getLogger(__name__)

ENDPOINT = os.environ.get("CAPTIONING_ENDPOINT") or "http://captioning:8080/v1/chat/completions"
API_KEY = os.environ.get("CAPTIONING_API_KEY", "")
API_MODEL = os.environ.get("CAPTIONING_API_MODEL", "")


def is_available() -> bool:
    return os.environ.get("CAPTIONING_ENABLED", "true").lower() == "true"


def get_config() -> dict:
    """Return captioning config safe for inclusion in warnings/logs."""
    return {
        "endpoint": ENDPOINT,
        "api_key": f"set ({len(API_KEY)} chars)" if API_KEY else "not set",
        "model": API_MODEL or "not set",
    }


async def _call(image_b64: str, mime_type: str, prompt: str, max_tokens: int, timeout: float) -> tuple[dict, float]:
    """Send a base64-encoded image to the captioning service."""
    payload: dict = {
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
    if API_MODEL:
        payload["model"] = API_MODEL

    headers = {}
    if API_KEY:
        headers["Authorization"] = f"Bearer {API_KEY}"

    async with httpx.AsyncClient(timeout=timeout) as client:
        start_time = time.time()
        try:
            response = await client.post(ENDPOINT, json=payload, headers=headers)
        except httpx.TimeoutException:
            raise HTTPException(status_code=504, detail="Captioning service timeout")
        except httpx.ConnectError:
            raise HTTPException(status_code=502, detail=f"Failed to reach captioning service at {ENDPOINT}")
        elapsed = (time.time() - start_time) * 1000

        if response.status_code != 200:
            raise HTTPException(
                status_code=502,
                detail=f"Captioning service error {response.status_code}: {response.text}",
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


async def transcribe(image_bytes: bytes, mime_type: str, timeout: float, debug: list[dict] | None = None) -> ConvertResult:
    """Transcribe an image of text, table, or handwriting."""
    if debug is None:
        debug = []
    image_bytes, mime_type = to_png(image_bytes, mime_type)
    image_b64 = base64.b64encode(image_bytes).decode("utf-8")
    raw, elapsed = await _call(image_b64, mime_type, TRANSCRIBE, max_tokens=1024, timeout=timeout)
    content = _extract_content(raw)
    debug.append({"step": "transcription", "elapsed_ms": elapsed, "output_length": len(content)})
    return ConvertResult(
        markdown=content,
        detected_type=mime_type,
        actions=["transcription"],
        processing_time_ms=elapsed,
        debug=debug,
    )
