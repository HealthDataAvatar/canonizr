from io import BytesIO

from PIL import Image

# MIME types the captioning VLM accepts natively — no conversion needed
NATIVE_TYPES = {
    "image/jpeg",
    "image/png",
}

MULTIPAGE_TYPES = {"image/tiff"}

MAX_DIMENSION = 4096


def _downscale(img: Image.Image) -> Image.Image:
    """Downscale to fit within MAX_DIMENSION, preserving aspect ratio."""
    if max(img.size) > MAX_DIMENSION:
        img.thumbnail((MAX_DIMENSION, MAX_DIMENSION), Image.Resampling.LANCZOS)
    return img


def to_native(image_bytes: bytes, mime_type: str) -> tuple[bytes, str]:
    """Convert image bytes to PNG if the format isn't natively supported by the VLM.
    Downscales if either dimension exceeds MAX_DIMENSION.
    Returns (converted_bytes, mime_type)."""
    img = Image.open(BytesIO(image_bytes))

    if mime_type in NATIVE_TYPES and max(img.size) <= MAX_DIMENSION:
        return image_bytes, mime_type

    _downscale(img)
    buf = BytesIO()
    img.convert("RGB").save(buf, format="PNG")
    return buf.getvalue(), "image/png"


def extract_pages(image_bytes: bytes) -> list[tuple[bytes, str]]:
    """Extract all pages from a multi-page image (e.g. TIFF) as PNG.
    Downscales pages that exceed MAX_DIMENSION.
    Returns a list of (image_bytes, mime_type) tuples."""
    img = Image.open(BytesIO(image_bytes))
    pages = []
    for i in range(getattr(img, "n_frames", 1)):
        img.seek(i)
        frame = img.convert("RGB")
        _downscale(frame)
        buf = BytesIO()
        frame.save(buf, format="PNG")
        pages.append((buf.getvalue(), "image/png"))
    return pages


def is_multipage(mime_type: str) -> bool:
    return mime_type in MULTIPAGE_TYPES
