"""Test MarkItDown conversion paths (DOCX, XLSX)."""
import io
import requests
from conftest import GATEWAY_URL, TIMEOUT, make_docx, make_xlsx


def test_docx():
    docx_bytes = make_docx("Integration test paragraph.")
    r = requests.post(
        f"{GATEWAY_URL}/convert",
        files={"file": ("test.docx", io.BytesIO(docx_bytes), "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
        timeout=TIMEOUT,
    )
    assert r.status_code == 200
    data = r.json()
    assert "Integration test paragraph" in data["markdown"]
    assert "markitdown" in data["metadata"]["actions"]


def test_xlsx():
    xlsx_bytes = make_xlsx()
    r = requests.post(
        f"{GATEWAY_URL}/convert",
        files={"file": ("test.xlsx", io.BytesIO(xlsx_bytes), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
        timeout=TIMEOUT,
    )
    assert r.status_code == 200
    data = r.json()
    assert "Alpha" in data["markdown"]
    assert "markitdown" in data["metadata"]["actions"]
