import asyncio
import functools

from io import BytesIO

from markitdown import MarkItDown

from .imageconv import extract_pages, is_multipage
from .response import ConvertResult
from .services import captioning, docling, libreoffice
from .tracing import Trace

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
    "application/vnd.oasis.opendocument.text": "docx",  # .odt → .docx
    "application/vnd.oasis.opendocument.presentation": "pdf",  # .odp → .pdf
    "application/vnd.oasis.opendocument.spreadsheet": "xlsx",  # .ods → .xlsx
    "application/vnd.apple.pages": "docx",  # .pages → .docx
    "application/vnd.apple.numbers": "xlsx",  # .numbers → .xlsx
    "application/vnd.apple.keynote": "pdf",  # .key → .pdf
}


async def convert(file_bytes: bytes, mime_type: str, filename: str, timeout: float, trace: Trace | None = None) -> ConvertResult:
    """Convert any supported file to markdown."""
    parent = trace.root if trace else None

    # Passthrough — already LLM-readable
    if mime_type in PASSTHROUGH_TYPES:
        if parent:
            with parent.span("passthrough"):
                pass
        return ConvertResult(
            markdown=file_bytes.decode("utf-8", errors="replace"),
            detected_type=mime_type,
            actions=["passthrough"],
        )

    # Images — describe via vision model
    if mime_type.startswith("image/"):
        if not captioning.is_available():
            raise ServiceNotConfigured(
                "Image processing requires the captioning service. "
                "Set CAPTIONING_ENABLED=true in .env and ensure the captioning container is running."
            )
        if is_multipage(mime_type):
            if parent:
                with parent.span("extract_pages") as ep_span:
                    pages = extract_pages(file_bytes)
                    ep_span.set(page_count=len(pages))
            else:
                pages = extract_pages(file_bytes)

            results = []
            for i, (p, mt) in enumerate(pages):
                if parent:
                    with parent.span(f"page[{i}]") as page_span:
                        r = await captioning.describe_file(p, mt, timeout, page_span)
                else:
                    r = await captioning.describe_file(p, mt, timeout)
                results.append(r)

            markdown = "\n\n---\n\n".join(r.markdown for r in results)
            return ConvertResult(
                markdown=markdown,
                detected_type=mime_type,
                actions=["captioning"],
                images_captioned=sum(r.images_captioned for r in results),
                captioning_prompt_tokens=sum(r.captioning_prompt_tokens for r in results),
                captioning_completion_tokens=sum(r.captioning_completion_tokens for r in results),
            )
        result = await captioning.describe_file(file_bytes, mime_type, timeout, parent)
        result.detected_type = mime_type
        return result

    # PDF — Docling for quality extraction
    if mime_type == "application/pdf":
        if parent:
            with parent.span("docling") as docling_span:
                return await docling.convert(file_bytes, mime_type, timeout, docling_span)
        return await docling.convert(file_bytes, mime_type, timeout)

    # Office docs MarkItDown handles directly
    if mime_type in MARKITDOWN_TYPES:
        loop = asyncio.get_event_loop()
        if parent:
            with parent.span("markitdown") as md_span:
                mit_result = await loop.run_in_executor(
                    None,
                    functools.partial(markitdown.convert_stream, BytesIO(file_bytes), file_extension=_ext_from_filename(filename)),
                )
                md_span.set(md_length=len(mit_result.text_content))
        else:
            mit_result = await loop.run_in_executor(
                None,
                functools.partial(markitdown.convert_stream, BytesIO(file_bytes), file_extension=_ext_from_filename(filename)),
            )
        return ConvertResult(
            markdown=mit_result.text_content,
            detected_type=mime_type,
            actions=["markitdown"],
        )

    # Legacy formats — LibreOffice converts, then re-process
    if mime_type in LIBREOFFICE_TYPES:
        if not libreoffice.is_available():
            raise ServiceNotConfigured(
                f"This file type ({mime_type}) requires LibreOffice. "
                "Rerun setup to enable it."
            )
        target = LIBREOFFICE_TYPES[mime_type]
        if parent:
            with parent.span("libreoffice", target_format=target) as lo_span:
                converted_bytes, converted_mime = await libreoffice.convert(
                    file_bytes, mime_type, filename, target, timeout, lo_span
                )
        else:
            converted_bytes, converted_mime = await libreoffice.convert(
                file_bytes, mime_type, filename, target, timeout
            )
        result = await convert(converted_bytes, converted_mime, filename, timeout, trace)
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
