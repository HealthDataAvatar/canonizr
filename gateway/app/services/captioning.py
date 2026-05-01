import base64
import json
import logging
import os
import time
from dataclasses import dataclass

import httpx
from fastapi import HTTPException

from ..imageconv import to_native
from ..prompts import IMAGE
from ..response import ConvertResult

logger = logging.getLogger(__name__)

ENDPOINT = os.environ.get("CAPTIONING_ENDPOINT") or "http://captioning:8080/v1/chat/completions"
API_KEY = os.environ.get("CAPTIONING_API_KEY", "")
API_MODEL = os.environ.get("CAPTIONING_API_MODEL", "")
_api_params_raw = os.environ.get("CAPTIONING_API_PARAMS", "")
API_PARAMS: dict = json.loads(_api_params_raw) if _api_params_raw else {"max_tokens": 1024}


def is_available() -> bool:
    return os.environ.get("CAPTIONING_ENABLED", "true").lower() == "true"


def get_config() -> dict:
    """Return captioning config safe for inclusion in warnings/logs."""
    return {
        "endpoint": ENDPOINT,
        "api_key": f"set ({len(API_KEY)} chars)" if API_KEY else "not set",
        "model": API_MODEL or "not set",
    }


@dataclass
class VisionResult:
    text: str
    prompt_tokens: int = 0
    completion_tokens: int = 0
    elapsed_ms: float = 0.0


async def _call(image_b64: str, mime_type: str, timeout: float) -> VisionResult:
    """Send a base64-encoded image to the vision service."""
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
                        "text": IMAGE,
                    },
                ],
            }
        ],
        **API_PARAMS,
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

        raw = response.json()
        text = raw.get("choices", [{}])[0].get("message", {}).get("content", "")
        usage = raw.get("usage", {})

        return VisionResult(
            text=text,
            prompt_tokens=usage.get("prompt_tokens", 0),
            completion_tokens=usage.get("completion_tokens", 0),
            elapsed_ms=elapsed,
        )


async def describe(image_b64: str, mime_type: str, timeout: float) -> VisionResult:
    """Describe an image from base64. Used for inline images in documents."""
    return await _call(image_b64, mime_type, timeout)


async def describe_file(image_bytes: bytes, mime_type: str, timeout: float, debug: list[dict] | None = None) -> ConvertResult:
    """Describe a standalone image upload."""
    if debug is None:
        debug = []
    image_bytes, mime_type = to_native(image_bytes, mime_type)
    image_b64 = base64.b64encode(image_bytes).decode("utf-8")
    result = await _call(image_b64, mime_type, timeout)
    debug.append({"step": "captioning", "elapsed_ms": result.elapsed_ms, "output_length": len(result.text)})
    return ConvertResult(
        markdown=result.text,
        detected_type=mime_type,
        actions=["captioning"],
        processing_time_ms=result.elapsed_ms,
        images_captioned=1,
        captioning_prompt_tokens=result.prompt_tokens,
        captioning_completion_tokens=result.completion_tokens,
        debug=debug,
    )
