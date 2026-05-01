import json

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ConvertResult:
    markdown: str
    detected_type: str = ""
    actions: list[str] = field(default_factory=list)
    trace: dict = field(default_factory=dict)
    processing_time_ms: float = 0.0
    input_bytes: int = 0
    input_hash: str = ""
    images_captioned: int = 0
    images_skipped: int = 0
    images_errored: int = 0
    captioning_prompt_tokens: int = 0
    captioning_completion_tokens: int = 0

    def to_dict(self, verbose: bool = False) -> dict[str, Any]:
        result: dict[str, Any] = {
            "markdown": self.markdown,
            "metadata": self._metadata(),
        }
        if verbose and self.trace:
            result["trace"] = self.trace
        return result

    def _metadata(self) -> dict[str, Any]:
        return {
            "detected_type": self.detected_type,
            "processing_time_ms": round(self.processing_time_ms),
            "input_bytes": self.input_bytes,
            "input_hash": self.input_hash,
            "captioning": {
                "images_captioned": self.images_captioned,
                "images_skipped": self.images_skipped,
                "images_errored": self.images_errored,
                "prompt_tokens": self.captioning_prompt_tokens,
                "completion_tokens": self.captioning_completion_tokens,
            },
            "actions": self.actions,
        }

    def metadata_json(self) -> str:
        """Compact JSON metadata for use in HTTP headers."""
        return json.dumps(self._metadata(), separators=(",", ":"))

    def audit_headers(self) -> dict[str, str]:
        """Headers for audit trail."""
        return {
            "X-Document-Hash": self.input_hash,
            "X-Input-Size-Bytes": str(self.input_bytes),
            "X-Images-Captioned": str(self.images_captioned),
            "X-Processing-Pipeline": ",".join(self.actions),
        }
