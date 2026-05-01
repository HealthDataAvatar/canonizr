"""Unit tests for the tracing module."""
from app.tracing import Trace


def test_trace_creates_root_span():
    t = Trace("request", mime_type="application/pdf")
    t.finish()
    d = t.to_dict()
    assert d["name"] == "request"
    assert d["attributes"]["mime_type"] == "application/pdf"
    assert "duration_ms" in d


def test_nested_spans():
    t = Trace("request")
    with t.span("docling") as docling_span:
        with docling_span.span("http_request", payload_bytes=1000) as http_span:
            http_span.set(status_code=200)
    t.finish()
    d = t.to_dict()
    assert len(d["children"]) == 1
    assert d["children"][0]["name"] == "docling"
    http = d["children"][0]["children"][0]
    assert http["name"] == "http_request"
    assert http["attributes"]["payload_bytes"] == 1000
    assert http["attributes"]["status_code"] == 200
    assert "duration_ms" in http


def test_span_set_merges_attributes():
    t = Trace("request")
    with t.span("step", a=1) as s:
        s.set(b=2, c=3)
    d = t.to_dict()
    attrs = d["children"][0]["attributes"]
    assert attrs == {"a": 1, "b": 2, "c": 3}


def test_empty_children_omitted():
    t = Trace("request")
    t.finish()
    d = t.to_dict()
    assert "children" not in d


def test_empty_attributes_omitted():
    t = Trace("request")
    with t.span("bare"):
        pass
    t.finish()
    d = t.to_dict()
    child = d["children"][0]
    assert "attributes" not in child
