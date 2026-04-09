from dataclasses import dataclass, field
from typing import Any


@dataclass
class ConvertResult:
    markdown: str
    detected_type: str = ""
    actions: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    debug: list[dict] = field(default_factory=list)
    processing_time_ms: float = 0.0
    images_captioned: int = 0
    images_skipped: int = 0

    def to_dict(self, verbose: bool = False) -> dict[str, Any]:
        result: dict[str, Any] = {
            "markdown": self.markdown,
            "metadata": {
                "detected_type": self.detected_type,
                "processing_time_ms": self.processing_time_ms,
                "images_captioned": self.images_captioned,
                "images_skipped": self.images_skipped,
                "actions": self.actions,
                "warnings": self.warnings,
            },
        }
        if verbose and self.debug:
            result["debug"] = self.debug
        return result
