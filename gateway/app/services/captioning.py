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
from ..tracing import Span

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


async def _call(image_b64: str, mime_type: str, timeout: float, parent: Span | None = None) -> VisionResult:
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

    payload_bytes = len(json.dumps(payload))

    async with httpx.AsyncClient(timeout=timeout) as client:
        http_span = None
        if parent is not None:
            http_span = Span(name="http_request", attributes={"payload_bytes": payload_bytes})
            http_span._start = time.monotonic()
            parent.children.append(http_span)

        start_time = time.time()
        try:
            response = await client.post(ENDPOINT, json=payload, headers=headers)
        except httpx.TimeoutException:
            if http_span:
                http_span._end = time.monotonic()
                http_span.set(error="timeout")
            raise HTTPException(status_code=504, detail="Captioning service timeout")
        except httpx.ConnectError:
            if http_span:
                http_span._end = time.monotonic()
                http_span.set(error="connect_failed")
            raise HTTPException(status_code=502, detail=f"Failed to reach captioning service at {ENDPOINT}")
        elapsed = (time.time() - start_time) * 1000

        if http_span:
            http_span._end = time.monotonic()
            http_span.set(response_bytes=len(response.content), status_code=response.status_code)

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


async def describe(image_b64: str, mime_type: str, timeout: float, parent: Span | None = None) -> VisionResult:
    """Describe an image from base64. Used for inline images in documents."""
    return await _call(image_b64, mime_type, timeout, parent)


async def describe_file(image_bytes: bytes, mime_type: str, timeout: float, parent: Span | None = None) -> ConvertResult:
    """Describe a standalone image upload."""
    input_size = len(image_bytes)
    if parent:
        with parent.span("image_convert", input_size_bytes=input_size) as s:
            image_bytes, mime_type = to_native(image_bytes, mime_type)
            s.set(output_size_bytes=len(image_bytes), output_mime=mime_type)
    else:
        image_bytes, mime_type = to_native(image_bytes, mime_type)

    image_b64 = base64.b64encode(image_bytes).decode("utf-8")
    result = await _call(image_b64, mime_type, timeout, parent)

    return ConvertResult(
        markdown=result.text,
        detected_type=mime_type,
        actions=["captioning"],
        processing_time_ms=result.elapsed_ms,
        images_captioned=1,
        captioning_prompt_tokens=result.prompt_tokens,
        captioning_completion_tokens=result.completion_tokens,
    )
