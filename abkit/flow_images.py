"""Stage 4 (CLAUDE.md, вариант флоу-скриншотов по группам): проверка типа
файла ПО СОДЕРЖИМОМУ (не по расширению/заявленному MIME) и санитизация через
пересохранение в Pillow — тот же принцип "не доверяй заявленному формату",
что и sql_guard.py для SQL (парсим и проверяем реальную структуру, а не
верим тому, что прислал клиент)."""

from __future__ import annotations

import io
from pathlib import Path

from PIL import Image, UnidentifiedImageError

MAX_FILE_BYTES = 5 * 1024 * 1024
MAX_IMAGES_PER_GROUP = 10
# Pillow's own format name -> (file extension, save format passed to Image.save).
# Only content Pillow itself identifies as one of these is accepted — a
# renamed .exe or an SVG (Pillow doesn't parse those into pixel data) never
# gets this far, regardless of what extension/Content-Type it arrived with.
_ALLOWED_FORMATS: dict[str, tuple[str, str]] = {
    "PNG": (".png", "PNG"),
    "JPEG": (".jpg", "JPEG"),
    "WEBP": (".webp", "WEBP"),
}
# Downscale cap for the on-disk copy — large phone screenshots have no
# reason to be stored/served at full resolution for a thumbnail+lightbox
# use case; also keeps design_report.html's base64-inlined copies small.
_MAX_DIMENSION = 1600


class FlowImageError(Exception):
    """Upload rejected: wrong/unrecognized content, too large, or too many
    already in the group. Caught by the router and turned into a 400."""


def validate_and_resave(raw: bytes, dest_stem: Path) -> Path:
    """Verifies raw is actually a supported image (by content, via Pillow —
    not by trusting the filename/Content-Type the client sent) and writes a
    SANITIZED re-encoded copy alongside dest_stem — re-saving through Pillow
    drops anything in the original bytes that isn't pixel data (embedded
    scripts, polyglot payloads, malformed metadata chunks a decoder further
    down the pipeline might mis-parse), the same defensive intent as
    re-hashing/re-parsing untrusted input elsewhere in this codebase.

    dest_stem: path WITHOUT extension — the real extension is only known
    once Pillow has identified the actual format, not from whatever the
    client's filename claimed, so the caller can't build the final path
    up front. Returns the full path actually written (dest_stem + the
    correct extension)."""
    if len(raw) > MAX_FILE_BYTES:
        raise FlowImageError(f"File exceeds the {MAX_FILE_BYTES // (1024 * 1024)} MB limit")

    try:
        with Image.open(io.BytesIO(raw)) as probe:
            probe.verify()  # cheap structural check; the image object is unusable after this
    except (UnidentifiedImageError, OSError, ValueError) as e:
        raise FlowImageError("File is not a valid PNG/JPEG/WEBP image") from e

    # verify() consumes the file object — re-open fresh for the real decode.
    with Image.open(io.BytesIO(raw)) as img:
        fmt = img.format
        if fmt not in _ALLOWED_FORMATS:
            raise FlowImageError(f"Unsupported image format '{fmt}' — use PNG, JPEG, or WEBP")
        ext, save_format = _ALLOWED_FORMATS[fmt]

        img.load()  # force full decode now, inside the try, not lazily later
        if img.width > _MAX_DIMENSION or img.height > _MAX_DIMENSION:
            img.thumbnail((_MAX_DIMENSION, _MAX_DIMENSION), Image.LANCZOS)

        # JPEG has no alpha channel — flatten onto white first, or Pillow
        # raises ("cannot write mode RGBA as JPEG") on a transparent PNG
        # saved-as-JPEG re-encode target (format is decided by the ORIGINAL
        # content's format, so this only fires for images that were already
        # JPEG-with-a-stray-alpha-mode, but cheap to guard unconditionally).
        if save_format == "JPEG" and img.mode in ("RGBA", "P"):
            img = img.convert("RGB")

        dest_path = dest_stem.with_suffix(ext)
        dest_path.parent.mkdir(parents=True, exist_ok=True)
        save_kwargs = {"quality": 85} if save_format in ("JPEG", "WEBP") else {}
        img.save(dest_path, format=save_format, **save_kwargs)
        return dest_path
