"""Unit tests for ConvertResult consumption reporting fields."""
import json

from app.response import ConvertResult


def test_metadata_includes_consumption_fields():
    result = ConvertResult(markdown="hello", input_bytes=12600, images_captioned=2, images_skipped=1, images_errored=0, images_failed=1)
    meta = result._metadata()
    assert meta["input_bytes"] == 12600
    assert meta["images_captioned"] == 2
    assert meta["images_skipped"] == 1
    assert meta["images_errored"] == 0
    assert meta["images_failed"] == 1


def test_metadata_defaults_zero():
    result = ConvertResult(markdown="")
    meta = result._metadata()
    assert meta["input_bytes"] == 0
    assert meta["images_errored"] == 0
    assert meta["images_failed"] == 0


def test_metadata_json_includes_input_bytes():
    result = ConvertResult(markdown="x", input_bytes=5632)
    parsed = json.loads(result.metadata_json())
    assert parsed["input_bytes"] == 5632


def test_to_dict_includes_metadata():
    result = ConvertResult(markdown="x", input_bytes=1024, images_failed=3)
    d = result.to_dict()
    assert d["metadata"]["input_bytes"] == 1024
    assert d["metadata"]["images_failed"] == 3
