"""Test captioning service paths."""
import io
import requests
from conftest import GATEWAY_URL, TIMEOUT, make_png, make_tiff


def test_image_returns_text():
    png_bytes = make_png("Hello World")
    r = requests.post(
        f"{GATEWAY_URL}/convert",
        files={"file": ("test.png", io.BytesIO(png_bytes), "image/png")},
        timeout=TIMEOUT,
    )
    assert r.status_code == 200
    data = r.json()
    assert len(data["markdown"]) > 0
    assert "captioning" in data["metadata"]["actions"]


def test_image_caption_not_empty():
    """If captioning is available, the response should contain actual text."""
    png_bytes = make_png("Test 123")
    r = requests.post(
        f"{GATEWAY_URL}/convert",
        files={"file": ("test.png", io.BytesIO(png_bytes), "image/png")},
        timeout=TIMEOUT,
    )
    assert r.status_code == 200
    data = r.json()
    assert len(data["markdown"].strip()) > 5


def test_multipage_tiff():
    """A multi-page TIFF should produce one section per page, separated by ---."""
    tiff_bytes = make_tiff(["Page One", "Page Two", "Page Three"])
    r = requests.post(
        f"{GATEWAY_URL}/convert",
        files={"file": ("scan.tiff", io.BytesIO(tiff_bytes), "image/tiff")},
        timeout=TIMEOUT,
    )
    assert r.status_code == 200
    data = r.json()
    sections = data["markdown"].split("---")
    assert len(sections) == 3
    for section in sections:
        assert len(section.strip()) > 0
    assert data["metadata"]["captioning"]["images_captioned"] == 3
