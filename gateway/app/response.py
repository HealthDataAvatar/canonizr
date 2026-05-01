import json

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ConvertResult:
    markdown: str
    detected_type: str = ""
    actions: list[str] = field(default_factory=list)
    warnings: list[dict] = field(default_factory=list)
    completeness: str = "full"
    debug: list[dict] = field(default_factory=list)
    processing_time_ms: float = 0.0
    input_kb: float = 0.0
    images_captioned: int = 0
    images_skipped: int = 0
    images_errored: int = 0
    images_failed: int = 0

    def to_dict(self, verbose: bool = False) -> dict[str, Any]:
        result: dict[str, Any] = {
            "markdown": self.markdown,
            "metadata": self._metadata(),
        }
        if verbose and self.debug:
            result["debug"] = self.debug
        return result

    def _metadata(self) -> dict[str, Any]:
        return {
            "detected_type": self.detected_type,
            "completeness": self.completeness,
            "processing_time_ms": round(self.processing_time_ms),
            "input_kb": self.input_kb,
            "images_captioned": self.images_captioned,
            "images_skipped": self.images_skipped,
            "images_errored": self.images_errored,
            "images_failed": self.images_failed,
            "actions": self.actions,
            "warnings": self.warnings,
        }

    def metadata_json(self) -> str:
        """Compact JSON metadata for use in HTTP headers."""
        return json.dumps(self._metadata(), separators=(",", ":"))
