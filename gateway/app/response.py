from dataclasses import dataclass, field


@dataclass
class ConvertResult:
    markdown: str
    detected_type: str = ""
    actions: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    processing_time_ms: float = 0.0
    images_captioned: int = 0
    images_skipped: int = 0

    def to_dict(self) -> dict:
        return {
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
