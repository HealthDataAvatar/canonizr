"""Unit tests for the /convert endpoint: headers, error sanitisation, echo headers."""
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from app.response import ConvertResult


def _mock_result():
    return ConvertResult(
        markdown="# Hello",
        detected_type="application/pdf",
        actions=["docling", "captioning"],
        input_bytes=2048,
        input_hash="abc123def456",
        images_captioned=3,
        images_skipped=1,
        images_errored=0,
    )


@pytest.fixture
def client():
    from app.app import app
    return TestClient(app)


class TestAuditHeaders:
    def test_json_response_has_audit_headers(self, client):
        with patch("app.app.convert", new_callable=AsyncMock, return_value=_mock_result()):
            resp = client.post("/convert", files={"file": ("test.pdf", b"%PDF-1.4 test", "application/pdf")})
        assert resp.status_code == 200
        assert len(resp.headers["X-Document-Hash"]) == 16
        assert resp.headers["X-Input-Size-Bytes"] == "13"
        assert resp.headers["X-Images-Captioned"] == "3"
        assert resp.headers["X-Processing-Pipeline"] == "docling,captioning"

    def test_markdown_response_has_audit_headers(self, client):
        with patch("app.app.convert", new_callable=AsyncMock, return_value=_mock_result()):
            resp = client.post(
                "/convert",
                files={"file": ("test.pdf", b"%PDF-1.4 test", "application/pdf")},
                headers={"Accept": "text/markdown"},
            )
        assert resp.status_code == 200
        assert len(resp.headers["X-Document-Hash"]) == 16


class TestEchoHeaders:
    def test_echoes_whitelisted_headers(self, client):
        with patch("app.app.convert", new_callable=AsyncMock, return_value=_mock_result()):
            resp = client.post(
                "/convert",
                files={"file": ("test.pdf", b"%PDF-1.4 test", "application/pdf")},
                headers={
                    "X-Subscription-Id": "sub_123",
                    "X-Org-Id": "org_456",
                    "X-Request-Id": "req_789",
                },
            )
        assert resp.headers["X-Subscription-Id"] == "sub_123"
        assert resp.headers["X-Org-Id"] == "org_456"
        assert resp.headers["X-Request-Id"] == "req_789"

    def test_does_not_echo_unknown_headers(self, client):
        with patch("app.app.convert", new_callable=AsyncMock, return_value=_mock_result()):
            resp = client.post(
                "/convert",
                files={"file": ("test.pdf", b"%PDF-1.4 test", "application/pdf")},
                headers={"X-Secret-Internal": "should_not_appear"},
            )
        assert "X-Secret-Internal" not in resp.headers


class TestErrorSanitisation:
    def test_production_sanitises_500(self, client):
        from app.services.image_postprocess import CaptioningUpstreamError
        err = CaptioningUpstreamError(0, Exception("Connection refused to http://captioning:8080"))
        with patch("app.app.convert", new_callable=AsyncMock, side_effect=err):
            with patch("app.app.DEBUG_MODE", False):
                resp = client.post("/convert", files={"file": ("test.pdf", b"%PDF-1.4 test", "application/pdf")})
        assert resp.status_code == 500
        assert "captioning:8080" not in resp.json()["detail"]
        assert resp.json()["detail"] == "Internal processing error"

    def test_debug_shows_full_error(self, client):
        from app.services.image_postprocess import CaptioningUpstreamError
        err = CaptioningUpstreamError(0, Exception("Connection refused to http://captioning:8080"))
        with patch("app.app.convert", new_callable=AsyncMock, side_effect=err):
            with patch("app.app.DEBUG_MODE", True):
                resp = client.post("/convert", files={"file": ("test.pdf", b"%PDF-1.4 test", "application/pdf")})
        assert resp.status_code == 500
        assert "captioning:8080" in resp.json()["detail"]

    def test_production_sanitises_502(self, client):
        from fastapi import HTTPException
        with patch("app.app.convert", new_callable=AsyncMock, side_effect=HTTPException(502, detail="Docling error: internal traceback here")):
            with patch("app.app.DEBUG_MODE", False):
                resp = client.post("/convert", files={"file": ("test.pdf", b"%PDF-1.4 test", "application/pdf")})
        assert resp.status_code == 502
        assert "traceback" not in resp.json()["detail"]
        assert resp.json()["detail"] == "Upstream service error"

    def test_400_not_sanitised(self, client):
        from app.convert import UnsupportedFormat
        with patch("app.app.convert", new_callable=AsyncMock, side_effect=UnsupportedFormat("video/mp4")):
            with patch("app.app.DEBUG_MODE", False):
                resp = client.post("/convert", files={"file": ("test.mp4", b"fake", "video/mp4")})
        assert resp.status_code == 400
        assert "video/mp4" in resp.json()["detail"]
