# File Types

What services are needed to properly process each file type.

The **Gateway** is always required — it handles routing, format detection, and response normalisation. MarkItDown and pymupdf are built into the gateway.

## Documents

| File type | Extensions | Services needed | Notes |
|---|---|---|---|
| PDF (digital) | `.pdf` | Docling | Text, tables, and layout extracted directly |
| PDF (scanned) | `.pdf` | Docling, Captioning | OCR via captioning for pages without a text layer |
| PDF with figures | `.pdf` | Docling, Captioning | Figures captioned; without Captioning they are stripped |
| DOCX | `.docx` | Gateway | MarkItDown handles natively |
| DOCX with figures | `.docx` | Gateway, Captioning | MarkItDown extracts text; embedded images sent to Captioning |
| DOC (legacy) | `.doc` | LibreOffice | Converted to DOCX, then MarkItDown extracts |
| RTF | `.rtf` | LibreOffice | Converted to DOCX, then MarkItDown extracts |
| ODT | `.odt` | Gateway | MarkItDown handles natively |
| PPTX | `.pptx` | Gateway | MarkItDown handles natively |
| PPT (legacy) | `.ppt` | LibreOffice | Converted to PPTX, then MarkItDown extracts |
| XLSX | `.xlsx` | Gateway | MarkItDown handles natively |
| XLS (legacy) | `.xls` | LibreOffice | Converted to XLSX, then MarkItDown extracts |
| ODP | `.odp` | LibreOffice, Docling | Converted to PDF, then Docling extracts |
| ODS | `.ods` | LibreOffice | Converted to XLSX, then MarkItDown extracts |
| EPUB | `.epub` | Gateway | MarkItDown handles natively |
| Pages (Apple) | `.pages` | LibreOffice | Converted to PDF/DOCX first |
| Numbers (Apple) | `.numbers` | LibreOffice | Converted to XLSX first |
| Keynote (Apple) | `.key` | LibreOffice | Converted to PDF first |

## Email

Emails are containers — the gateway parses the MIME structure, extracts the body, and recursively processes attachments through the appropriate services.

| File type | Extensions | Services needed | Notes |
|---|---|---|---|
| Email (standard) | `.eml` | Gateway | Parsed with Python stdlib `email` module; HTML body converted to markdown |
| Email (Outlook) | `.msg` | Gateway | MarkItDown handles natively |
| Email with attachments | `.eml`, `.msg` | Gateway + whatever the attachments need | Attachments routed through the pipeline individually |

## Already LLM-readable

These formats are plain text and can be read directly by any LLM. Canonizr will accept them but passes them through without transformation.

| File type | Extensions |
|---|---|
| Plain text | `.txt` |
| Markdown | `.md` |
| CSV | `.csv` |
| JSON | `.json` |
| XML | `.xml` |
| HTML | `.html`, `.htm` |
| LaTeX | `.tex` |
| Source code | `.py`, `.js`, `.ts`, `.go`, `.rs`, `.java`, etc. |

## Images

All image formats are converted to PNG if needed, then passed to the captioning service for description or transcription.

| File type | Extensions | Services needed |
|---|---|---|
| Images | `.jpg`, `.jpeg`, `.png`, `.webp`, `.gif`, `.tiff`, `.tif`, `.bmp`, `.heic`, `.ico` | Captioning |

## Service reference

| Service | What it does | Docker image |
|---|---|---|
| **Gateway** | Routing, format detection, orchestration, MarkItDown, pymupdf, Pillow | Built from `gateway/` |
| **Docling** | PDF layout analysis, table extraction, figure classification | Built from `docling/` |
| **Captioning** | Image captioning and transcription via VLM | `ghcr.io/ggml-org/llama.cpp:server` |
| **LibreOffice** | Legacy and complex format conversion (DOC, PPT, XLS, ODP, ODS, Apple formats) | TBD |
