import time

from io import BytesIO

from markitdown import MarkItDown

from .response import ConvertResult
from .services import captioning, docling, libreoffice

markitdown = MarkItDown()

# Formats any LLM can read directly — no conversion needed
PASSTHROUGH_TYPES = {
    "text/plain",
    "text/markdown",
    "text/csv",
    "text/x-python",
    "text/x-java",
    "text/x-c",
    "text/x-script.python",
    "application/json",
    "application/xml",
    "text/xml",
    "text/html",
}

# Formats MarkItDown handles natively
MARKITDOWN_TYPES = {
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",  # .docx
    "application/vnd.openxmlformats-officedocument.presentationml.presentation",  # .pptx
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",  # .xlsx
    "application/vnd.oasis.opendocument.text",  # .odt
    "application/epub+zip",  # .epub
    "message/rfc822",  # .eml
    "application/vnd.ms-outlook",  # .msg
}

# Formats that need LibreOffice to convert first
LIBREOFFICE_TYPES = {
    "application/msword": "docx",  # .doc → .docx
    "application/rtf": "docx",  # .rtf → .docx
    "text/rtf": "docx",  # .rtf → .docx (alternate MIME)
    "application/vnd.ms-powerpoint": "pptx",  # .ppt → .pptx
    "application/vnd.ms-excel": "xlsx",  # .xls → .xlsx
    "application/vnd.oasis.opendocument.presentation": "pdf",  # .odp → .pdf
    "application/vnd.oasis.opendocument.spreadsheet": "xlsx",  # .ods → .xlsx
    "application/vnd.apple.pages": "docx",  # .pages → .docx
    "application/vnd.apple.numbers": "xlsx",  # .numbers → .xlsx
    "application/vnd.apple.keynote": "pdf",  # .key → .pdf
}


async def convert(file_bytes: bytes, mime_type: str, filename: str, timeout: float) -> ConvertResult:
    """Convert any supported file to markdown."""
    start_time = time.time()

    # Passthrough — already LLM-readable
    if mime_type in PASSTHROUGH_TYPES:
        return ConvertResult(
            markdown=file_bytes.decode("utf-8", errors="replace"),
            detected_type=mime_type,
            actions=["passthrough"],
            processing_time_ms=(time.time() - start_time) * 1000,
        )

    # Images — caption or transcribe
    if mime_type.startswith("image/"):
        if not captioning.is_available():
            raise ServiceNotConfigured(
                "Image processing requires the captioning service. "
                "Set CAPTIONING_ENABLED=true in .env and ensure the captioning container is running."
            )
        result = await captioning.transcribe(file_bytes, mime_type, timeout)
        result.detected_type = mime_type
        return result

    # PDF — Docling for quality extraction
    if mime_type == "application/pdf":
        return await docling.convert(file_bytes, mime_type, timeout)

    # Office docs MarkItDown handles directly
    if mime_type in MARKITDOWN_TYPES:
        result = markitdown.convert_stream(BytesIO(file_bytes), file_extension=_ext_from_filename(filename))
        return ConvertResult(
            markdown=result.text_content,
            detected_type=mime_type,
            actions=["markitdown"],
            processing_time_ms=(time.time() - start_time) * 1000,
        )

    # Legacy formats — LibreOffice converts, then re-process
    if mime_type in LIBREOFFICE_TYPES:
        target = LIBREOFFICE_TYPES[mime_type]
        converted_bytes, converted_mime = await libreoffice.convert(
            file_bytes, mime_type, filename, target, timeout
        )
        result = await convert(converted_bytes, converted_mime, filename, timeout)
        result.actions.insert(0, f"libreoffice ({mime_type} → {target})")
        result.detected_type = mime_type
        return result

    raise UnsupportedFormat(mime_type)


def _ext_from_filename(filename: str) -> str:
    """Extract file extension from filename."""
    if "." in filename:
        return "." + filename.rsplit(".", 1)[-1].lower()
    return ""


class UnsupportedFormat(Exception):
    def __init__(self, mime_type: str):
        self.mime_type = mime_type
        super().__init__(f"Unsupported file type: {mime_type}")


class ServiceNotConfigured(Exception):
    def __init__(self, message: str):
        super().__init__(message)
