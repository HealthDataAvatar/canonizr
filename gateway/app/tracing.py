"""Lightweight structured tracing for pipeline observability."""
from __future__ import annotations

import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any, Generator


@dataclass
class Span:
    name: str
    attributes: dict[str, Any] = field(default_factory=dict)
    children: list[Span] = field(default_factory=list)
    _start: float = field(default=0.0, repr=False)
    _end: float | None = field(default=None, repr=False)

    @property
    def duration_ms(self) -> float | None:
        if self._end is None:
            return None
        return (self._end - self._start) * 1000

    @contextmanager
    def span(self, name: str, **attrs: Any) -> Generator[Span, None, None]:
        child = Span(name=name, attributes=attrs, _start=time.monotonic())
        self.children.append(child)
        try:
            yield child
        finally:
            child._end = time.monotonic()

    def set(self, **attrs: Any) -> None:
        self.attributes.update(attrs)

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {"name": self.name}
        duration = self.duration_ms
        if duration is not None:
            result["duration_ms"] = round(duration, 1)
        if self.attributes:
            result["attributes"] = self.attributes
        if self.children:
            result["children"] = [c.to_dict() for c in self.children]
        return result


class Trace:
    """Root trace container. Create one per request."""

    def __init__(self, name: str = "request", **attrs: Any):
        self.root = Span(name=name, attributes=attrs, _start=time.monotonic())

    def span(self, name: str, **attrs: Any):
        return self.root.span(name, **attrs)

    def finish(self) -> None:
        self.root._end = time.monotonic()

    def to_dict(self) -> dict[str, Any]:
        return self.root.to_dict()
