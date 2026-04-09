"""Test captioning service paths."""
import io
import requests
from conftest import GATEWAY_URL, TIMEOUT, make_png


def test_image_returns_text():
    png_bytes = make_png("Hello World")
    r = requests.post(
        f"{GATEWAY_URL}/convert",
        files={"file": ("test.png", io.BytesIO(png_bytes), "image/png")},
        timeout=TIMEOUT,
    )
    # 200 if transcription is running, 422 if disabled
    assert r.status_code in [200, 422]

    if r.status_code == 200:
        data = r.json()
        assert len(data["markdown"]) > 0
        assert "transcription" in data["metadata"]["actions"]


def test_image_caption_not_empty():
    """If captioning is available, the response should contain actual text."""
    png_bytes = make_png("Test 123")
    r = requests.post(
        f"{GATEWAY_URL}/convert",
        files={"file": ("test.png", io.BytesIO(png_bytes), "image/png")},
        timeout=TIMEOUT,
    )
    if r.status_code == 200:
        data = r.json()
        # Should be more than just whitespace
        assert len(data["markdown"].strip()) > 5
