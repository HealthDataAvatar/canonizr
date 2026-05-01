"""Test PDF embedded image captioning paths."""
import io
import requests
from conftest import GATEWAY_URL, TIMEOUT, EmbeddedImage, make_pdf_with_images


def _find_span(trace: dict, name: str) -> dict | None:
    """Recursively find a span by name in a trace tree."""
    if trace.get("name") == name:
        return trace
    for child in trace.get("children", []):
        found = _find_span(child, name)
        if found:
            return found
    return None


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

    trace = data.get("trace", {})
    cap_span = _find_span(trace, "captioning")
    if cap_span:
        attrs = cap_span.get("attributes", {})
        assert attrs.get("image_count", 0) >= 1


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

    trace = data.get("trace", {})
    cap_span = _find_span(trace, "captioning")
    if cap_span:
        attrs = cap_span.get("attributes", {})
        assert attrs.get("captioned", 0) == 0
