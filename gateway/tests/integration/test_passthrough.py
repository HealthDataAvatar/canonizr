"""Test that LLM-readable formats pass through without transformation."""
import io
import requests
from conftest import GATEWAY_URL, TIMEOUT


def test_plain_text():
    content = b"Hello, this is plain text."
    r = requests.post(
        f"{GATEWAY_URL}/convert",
        files={"file": ("test.txt", io.BytesIO(content), "text/plain")},
        timeout=TIMEOUT,
    )
    assert r.status_code == 200
    data = r.json()
    assert "Hello" in data["markdown"]
    assert "passthrough" in data["metadata"]["actions"]


def test_markdown():
    content = b"# Heading\n\nA paragraph.\n"
    r = requests.post(
        f"{GATEWAY_URL}/convert",
        files={"file": ("test.md", io.BytesIO(content), "text/markdown")},
        timeout=TIMEOUT,
    )
    assert r.status_code == 200
    data = r.json()
    assert "# Heading" in data["markdown"]
    assert "passthrough" in data["metadata"]["actions"]


def test_json():
    content = b'{"key": "value", "number": 42}'
    r = requests.post(
        f"{GATEWAY_URL}/convert",
        files={"file": ("test.json", io.BytesIO(content), "application/json")},
        timeout=TIMEOUT,
    )
    assert r.status_code == 200
    data = r.json()
    assert "key" in data["markdown"]
    assert "passthrough" in data["metadata"]["actions"]


def test_csv():
    content = b"name,value\nalpha,10\nbeta,20\n"
    r = requests.post(
        f"{GATEWAY_URL}/convert",
        files={"file": ("test.csv", io.BytesIO(content), "text/csv")},
        timeout=TIMEOUT,
    )
    assert r.status_code == 200
    data = r.json()
    assert "alpha" in data["markdown"]
    assert "passthrough" in data["metadata"]["actions"]
