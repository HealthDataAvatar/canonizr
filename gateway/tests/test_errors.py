"""Test error handling."""
import io
import requests
from conftest import GATEWAY_URL, TIMEOUT


def test_unsupported_format():
    garbage = b'\x00\x01\x02\x03\x04\x05\x06\x07'
    r = requests.post(
        f"{GATEWAY_URL}/convert",
        files={"file": ("test.xyz", io.BytesIO(garbage), "application/octet-stream")},
        timeout=TIMEOUT,
    )
    assert r.status_code == 400
    assert "Unsupported" in r.json()["detail"]


def test_file_too_large():
    large_data = b'\x00' * (51 * 1024 * 1024)
    r = requests.post(
        f"{GATEWAY_URL}/convert",
        files={"file": ("large.pdf", io.BytesIO(large_data), "application/pdf")},
        timeout=TIMEOUT,
    )
    assert r.status_code == 413
    assert "too large" in r.json()["detail"].lower()


def test_empty_file():
    r = requests.post(
        f"{GATEWAY_URL}/convert",
        files={"file": ("empty.txt", io.BytesIO(b""), "text/plain")},
        timeout=TIMEOUT,
    )
    # Should succeed with empty markdown, not crash
    assert r.status_code == 200
