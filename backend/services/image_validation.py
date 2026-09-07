"""
Image upload validation (brief PART 21 / NFR-2,3): MIME + magic-byte checks,
size cap, and EXIF/GPS stripping. Validates the *actual bytes*, not just the
filename or the client-supplied Content-Type — a renamed .txt claiming to be
image/jpeg must be rejected, not trusted.
"""
from __future__ import annotations

import hashlib
import io
from dataclasses import dataclass

import magic
from PIL import Image, UnidentifiedImageError

from backend.errors import payload_too_large, unsupported_media, validation_error

# Maps the true, magic-byte-detected MIME type to the Pillow format string we
# expect for it. Anything not in this map is rejected regardless of what the
# browser claimed in its Content-Type header.
_ALLOWED_MIME_TO_PIL_FORMAT = {
    "image/jpeg": "JPEG",
    "image/png": "PNG",
    "image/webp": "WEBP",
}


@dataclass
class ValidatedImage:
    clean_bytes: bytes  # re-encoded, EXIF/GPS-stripped
    width: int
    height: int
    sha256_hex: str
    original_mime: str


def validate_and_clean_image(
    raw_bytes: bytes, max_size_mb: int, allowed_mime_types: list[str]
) -> ValidatedImage:
    max_bytes = max_size_mb * 1024 * 1024
    if len(raw_bytes) > max_bytes:
        raise payload_too_large(f"Image exceeds the {max_size_mb} MB limit.")
    if len(raw_bytes) == 0:
        raise validation_error("Uploaded file is empty.")

    # Magic-byte detection — this inspects the actual file content, so a
    # renamed .txt or a polyglot file is caught here even if its extension
    # and client-supplied Content-Type both claim to be an image.
    detected_mime = magic.from_buffer(raw_bytes, mime=True)
    if detected_mime not in allowed_mime_types or detected_mime not in _ALLOWED_MIME_TO_PIL_FORMAT:
        raise unsupported_media(
            f"Unsupported file type ({detected_mime}). Please upload a JPEG, PNG, or WebP image."
        )

    try:
        img = Image.open(io.BytesIO(raw_bytes))
        img.verify()  # raises if the file is truncated / not a genuine image
        # verify() invalidates the image object for further use, so reopen it.
        img = Image.open(io.BytesIO(raw_bytes))
        img.load()
    except UnidentifiedImageError:
        raise unsupported_media("The uploaded file could not be read as an image.")
    except Exception:
        raise unsupported_media("The uploaded image appears to be corrupted.")

    width, height = img.size

    # Re-encode from decoded pixel data rather than passing the original
    # bytes through: this drops EXIF (including GPS) and any non-image data
    # a polyglot file might have smuggled in alongside valid image bytes.
    if img.mode not in ("RGB", "L"):
        img = img.convert("RGB")
    clean_buffer = io.BytesIO()
    save_format = _ALLOWED_MIME_TO_PIL_FORMAT[detected_mime]
    img.save(clean_buffer, format=save_format)
    clean_bytes = clean_buffer.getvalue()

    sha256_hex = hashlib.sha256(clean_bytes).hexdigest()

    return ValidatedImage(
        clean_bytes=clean_bytes,
        width=width,
        height=height,
        sha256_hex=sha256_hex,
        original_mime=detected_mime,
    )
