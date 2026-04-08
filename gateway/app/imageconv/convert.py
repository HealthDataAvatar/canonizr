from io import BytesIO

from PIL import Image

# MIME types the captioning VLM accepts natively — no conversion needed
NATIVE_TYPES = {
    "image/jpeg",
    "image/png",
    "image/webp",
    "image/gif",
    "image/bmp",
    "image/tiff",
}


def to_png(image_bytes: bytes, mime_type: str) -> tuple[bytes, str]:
    """Convert image bytes to PNG if the format isn't natively supported by the VLM.
    Returns (converted_bytes, mime_type)."""
    if mime_type in NATIVE_TYPES:
        return image_bytes, mime_type

    img = Image.open(BytesIO(image_bytes))
    buf = BytesIO()
    img.convert("RGB").save(buf, format="PNG")
    return buf.getvalue(), "image/png"
