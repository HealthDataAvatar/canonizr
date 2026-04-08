"""Test Docling PDF extraction paths."""
import io
import requests
from conftest import GATEWAY_URL, TIMEOUT, make_pdf


def test_pdf_text():
    pdf_bytes = make_pdf("Extract this sentence from the PDF.")
    r = requests.post(
        f"{GATEWAY_URL}/convert",
        files={"file": ("test.pdf", io.BytesIO(pdf_bytes), "application/pdf")},
        timeout=TIMEOUT,
    )
    assert r.status_code == 200
    data = r.json()
    assert len(data["markdown"]) > 0
    assert "docling" in data["metadata"]["actions"]


def test_pdf_multipage():
    pdf_bytes = make_pdf("Page content here.", pages=3)
    r = requests.post(
        f"{GATEWAY_URL}/convert",
        files={"file": ("multipage.pdf", io.BytesIO(pdf_bytes), "application/pdf")},
        timeout=TIMEOUT,
    )
    assert r.status_code == 200
    data = r.json()
    assert len(data["markdown"]) > 0
