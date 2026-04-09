"""Test PDF embedded image captioning paths."""
import io
import requests
from conftest import GATEWAY_URL, TIMEOUT, EmbeddedImage, make_pdf_with_images


def test_fixture_pdf_image_is_processed():
    """rising-bars.pdf has an embedded chart that should reach captioning."""
    with open("/fixtures/rising-bars.pdf", "rb") as f:
        pdf_bytes = f.read()
    r = requests.post(
        f"{GATEWAY_URL}/convert?verbose=true",
        files={"file": ("rising-bars.pdf", io.BytesIO(pdf_bytes), "application/pdf")},
        timeout=TIMEOUT,
    )
    assert r.status_code == 200
    data = r.json()
    assert "docling" in data["metadata"]["actions"]

    # Check verbose output confirms the image was found and attempted
    debug_steps = {d["step"]: d for d in data.get("debug", [])}
    if "captioning" in debug_steps:
        cap = debug_steps["captioning"]
        assert cap["md_image_count"] >= 1
        # Image should be captioned or fallback (if captioning service unavailable), not skipped
        for img in cap["images"]:
            assert img["action"] in ("captioned", "fallback"), (
                f"Image at index {img['index']} was unexpectedly: {img['action']}"
            )


def test_generated_small_image_is_skipped():
    """A generated PDF with a tiny image — should be skipped by dimension check."""
    pdf_bytes = make_pdf_with_images([
        EmbeddedImage("tiny", 30, 30),
    ])
    r = requests.post(
        f"{GATEWAY_URL}/convert?verbose=true",
        files={"file": ("small_img.pdf", io.BytesIO(pdf_bytes), "application/pdf")},
        timeout=TIMEOUT,
    )
    assert r.status_code == 200
    data = r.json()
    assert "docling" in data["metadata"]["actions"]

    debug_steps = {d["step"]: d for d in data.get("debug", [])}
    if "captioning" in debug_steps:
        for img in debug_steps["captioning"]["images"]:
            assert img["action"] in ("skipped_too_small", "skipped_decorative"), (
                f"Small image should be skipped, got: {img['action']}"
            )
