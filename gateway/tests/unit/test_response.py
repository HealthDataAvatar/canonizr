"""Unit tests for ConvertResult metadata and audit headers."""
import json

from app.response import ConvertResult


def test_metadata_includes_captioning_object():
    result = ConvertResult(
        markdown="hello", input_bytes=12600,
        images_captioned=2, images_skipped=1, images_errored=0,
        captioning_prompt_tokens=800, captioning_completion_tokens=50,
    )
    meta = result._metadata()
    assert meta["input_bytes"] == 12600
    cap = meta["captioning"]
    assert cap["images_captioned"] == 2
    assert cap["images_skipped"] == 1
    assert cap["images_errored"] == 0
    assert cap["prompt_tokens"] == 800
    assert cap["completion_tokens"] == 50


def test_metadata_defaults_zero():
    result = ConvertResult(markdown="")
    meta = result._metadata()
    assert meta["input_bytes"] == 0
    cap = meta["captioning"]
    assert cap["images_errored"] == 0
    assert cap["prompt_tokens"] == 0
    assert cap["completion_tokens"] == 0


def test_metadata_json_includes_input_bytes():
    result = ConvertResult(markdown="x", input_bytes=5632)
    parsed = json.loads(result.metadata_json())
    assert parsed["input_bytes"] == 5632


def test_to_dict_includes_captioning():
    result = ConvertResult(markdown="x", input_bytes=1024, images_errored=3, captioning_prompt_tokens=100)
    d = result.to_dict()
    assert d["metadata"]["input_bytes"] == 1024
    assert d["metadata"]["captioning"]["images_errored"] == 3
    assert d["metadata"]["captioning"]["prompt_tokens"] == 100


def test_to_dict_includes_trace_when_verbose():
    result = ConvertResult(markdown="x", trace={"name": "request", "duration_ms": 100})
    d = result.to_dict(verbose=True)
    assert d["trace"]["name"] == "request"
    assert d["trace"]["duration_ms"] == 100


def test_to_dict_excludes_trace_when_not_verbose():
    result = ConvertResult(markdown="x", trace={"name": "request"})
    d = result.to_dict(verbose=False)
    assert "trace" not in d


def test_audit_headers():
    result = ConvertResult(
        markdown="x",
        input_bytes=2048,
        input_hash="abc123",
        images_captioned=5,
        actions=["docling", "captioning"],
    )
    headers = result.audit_headers()
    assert headers["X-Document-Hash"] == "abc123"
    assert headers["X-Input-Size-Bytes"] == "2048"
    assert headers["X-Images-Captioned"] == "5"
    assert headers["X-Processing-Pipeline"] == "docling,captioning"
