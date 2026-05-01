import asyncio
import logging
import os
import random
import time

import httpx
from fastapi import HTTPException

from ..tracing import Span

logger = logging.getLogger(__name__)

MAX_RETRIES = int(os.environ.get("UPSTREAM_MAX_RETRIES", "2"))
_BACKOFF_BASE = 1.0
_BACKOFF_MAX = 60.0
_RETRY_STATUSES = {429, 500, 502, 503, 504}


def _remaining(deadline: float) -> float:
    return max(deadline - time.monotonic(), 0.0)


def _backoff_delay(attempt: int, retry_after: str | None) -> float:
    """Compute delay: prefer Retry-After header, fall back to exponential backoff + jitter."""
    if retry_after is not None:
        try:
            delay = float(retry_after)
            return min(max(delay, 0.0), _BACKOFF_MAX)
        except (ValueError, OverflowError):
            pass
    delay = _BACKOFF_BASE * (2 ** attempt) + random.uniform(0, 1)
    return min(delay, _BACKOFF_MAX)


async def request_with_retry(
    client: httpx.AsyncClient,
    method: str,
    url: str,
    *,
    deadline: float,
    service_name: str = "upstream",
    max_retries: int = MAX_RETRIES,
    span: Span | None = None,
    **kwargs,
) -> httpx.Response:
    """Make an HTTP request with retry on 429/5xx, bounded by a wall-clock deadline."""
    last_response: httpx.Response | None = None

    for attempt in range(1 + max_retries):
        remaining = _remaining(deadline)
        if remaining <= 0:
            break

        # Shrink per-request timeout to fit within deadline
        client.timeout = httpx.Timeout(remaining)

        try:
            response = await client.request(method, url, **kwargs)
        except httpx.TimeoutException:
            if span:
                span.set(error="timeout", retry_attempt=attempt)
            raise HTTPException(status_code=504, detail=f"{service_name} service timeout")
        except httpx.RequestError as e:
            if span:
                span.set(error=str(e), retry_attempt=attempt)
            raise HTTPException(status_code=502, detail=f"Failed to reach {service_name}: {e}")

        if span:
            span.set(status_code=response.status_code, response_bytes=len(response.content))

        if response.status_code not in _RETRY_STATUSES:
            return response

        last_response = response
        if attempt < max_retries:
            delay = _backoff_delay(attempt, response.headers.get("retry-after"))
            remaining = _remaining(deadline)
            if delay > remaining:
                break
            logger.info(
                "%s returned %d, retrying in %.1fs (attempt %d/%d)",
                service_name, response.status_code, delay, attempt + 1, max_retries,
            )
            if span:
                span.set(**{f"retry_{attempt}_status": response.status_code, f"retry_{attempt}_delay": round(delay, 2)})
            await asyncio.sleep(delay)

    # Retries exhausted or deadline reached
    if last_response is not None:
        status = last_response.status_code
        if status == 429:
            raise HTTPException(status_code=429, detail=f"{service_name} rate limit exceeded")
        raise HTTPException(
            status_code=502,
            detail=f"{service_name} service error {status}: {last_response.text}",
        )

    raise HTTPException(status_code=504, detail=f"{service_name} request deadline exceeded")
