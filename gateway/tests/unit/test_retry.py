"""Unit tests for the retry utility."""
import time

import httpx
import pytest

from fastapi import HTTPException

from app.services.retry import request_with_retry, _backoff_delay


def _deadline(seconds: float) -> float:
    return time.monotonic() + seconds


class _MockTransport(httpx.AsyncBaseTransport):
    """Returns canned responses in sequence."""

    def __init__(self, responses: list[httpx.Response]):
        self._responses = list(responses)
        self._calls = 0

    async def handle_async_request(self, request):
        idx = min(self._calls, len(self._responses) - 1)
        self._calls += 1
        return self._responses[idx]

    @property
    def call_count(self):
        return self._calls


def _response(status: int, headers: dict | None = None) -> httpx.Response:
    return httpx.Response(status, headers=headers or {}, content=b"error")


@pytest.mark.asyncio
async def test_success_no_retry():
    transport = _MockTransport([_response(200)])
    async with httpx.AsyncClient(transport=transport) as client:
        resp = await request_with_retry(
            client, "POST", "http://test/api",
            deadline=_deadline(10),
        )
    assert resp.status_code == 200
    assert transport.call_count == 1


@pytest.mark.asyncio
async def test_retry_on_429_then_success():
    transport = _MockTransport([
        _response(429, {"retry-after": "0.01"}),
        _response(200),
    ])
    async with httpx.AsyncClient(transport=transport) as client:
        resp = await request_with_retry(
            client, "POST", "http://test/api",
            deadline=_deadline(10),
        )
    assert resp.status_code == 200
    assert transport.call_count == 2


@pytest.mark.asyncio
async def test_retry_on_503_then_success():
    transport = _MockTransport([
        _response(503),
        _response(200),
    ])
    async with httpx.AsyncClient(transport=transport) as client:
        resp = await request_with_retry(
            client, "POST", "http://test/api",
            deadline=_deadline(10),
        )
    assert resp.status_code == 200
    assert transport.call_count == 2


@pytest.mark.asyncio
async def test_exhausted_retries_429_raises_429():
    transport = _MockTransport([
        _response(429),
        _response(429),
        _response(429),
    ])
    async with httpx.AsyncClient(transport=transport) as client:
        with pytest.raises(HTTPException) as exc_info:
            await request_with_retry(
                client, "POST", "http://test/api",
                deadline=_deadline(30),
                max_retries=2,
            )
    assert exc_info.value.status_code == 429


@pytest.mark.asyncio
async def test_exhausted_retries_502_raises_502():
    transport = _MockTransport([
        _response(502),
        _response(502),
        _response(502),
    ])
    async with httpx.AsyncClient(transport=transport) as client:
        with pytest.raises(HTTPException) as exc_info:
            await request_with_retry(
                client, "POST", "http://test/api",
                deadline=_deadline(30),
                max_retries=2,
            )
    assert exc_info.value.status_code == 502


@pytest.mark.asyncio
async def test_deadline_exceeded_stops_retries():
    transport = _MockTransport([
        _response(429, {"retry-after": "100"}),
        _response(200),
    ])
    async with httpx.AsyncClient(transport=transport) as client:
        with pytest.raises(HTTPException) as exc_info:
            await request_with_retry(
                client, "POST", "http://test/api",
                deadline=_deadline(0.1),
                max_retries=5,
            )
    # Should not have retried because retry-after exceeds deadline
    assert transport.call_count == 1
    assert exc_info.value.status_code == 429


@pytest.mark.asyncio
async def test_no_retry_on_4xx():
    """Non-429 client errors should not be retried."""
    transport = _MockTransport([_response(400)])
    async with httpx.AsyncClient(transport=transport) as client:
        resp = await request_with_retry(
            client, "POST", "http://test/api",
            deadline=_deadline(10),
        )
    assert resp.status_code == 400
    assert transport.call_count == 1


@pytest.mark.asyncio
async def test_zero_retries_propagates_immediately():
    transport = _MockTransport([_response(429)])
    async with httpx.AsyncClient(transport=transport) as client:
        with pytest.raises(HTTPException) as exc_info:
            await request_with_retry(
                client, "POST", "http://test/api",
                deadline=_deadline(10),
                max_retries=0,
            )
    assert exc_info.value.status_code == 429
    assert transport.call_count == 1


def test_backoff_delay_respects_retry_after():
    delay = _backoff_delay(0, "5.0")
    assert delay == 5.0


def test_backoff_delay_caps_retry_after():
    delay = _backoff_delay(0, "999")
    assert delay == 60.0


def test_backoff_delay_exponential_fallback():
    delay = _backoff_delay(0, None)
    assert 1.0 <= delay <= 2.0  # base=1 * 2^0 + jitter(0,1)
    delay = _backoff_delay(2, None)
    assert 4.0 <= delay <= 5.0  # base=1 * 2^2 + jitter(0,1)
