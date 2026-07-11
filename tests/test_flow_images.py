"""Stage 4 (CLAUDE.md, variant flow images): content-based validation +
Pillow re-save sanitization, independent of the DB/API layers."""

import io

import pytest
from PIL import Image

from abkit.flow_images import MAX_FILE_BYTES, FlowImageError, validate_and_resave


def _png_bytes(size=(20, 20), color=(255, 0, 0)) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", size, color).save(buf, format="PNG")
    return buf.getvalue()


def _jpeg_bytes(size=(20, 20)) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", size, (0, 255, 0)).save(buf, format="JPEG")
    return buf.getvalue()


def _webp_bytes(size=(20, 20)) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", size, (0, 0, 255)).save(buf, format="WEBP")
    return buf.getvalue()


def test_valid_png_is_saved_with_png_extension(tmp_path):
    dest = validate_and_resave(_png_bytes(), tmp_path / "img")
    assert dest.suffix == ".png"
    assert dest.exists()
    with Image.open(dest) as saved:
        assert saved.format == "PNG"


def test_valid_jpeg_is_saved_with_jpg_extension(tmp_path):
    dest = validate_and_resave(_jpeg_bytes(), tmp_path / "img")
    assert dest.suffix == ".jpg"
    with Image.open(dest) as saved:
        assert saved.format == "JPEG"


def test_valid_webp_is_saved_with_webp_extension(tmp_path):
    dest = validate_and_resave(_webp_bytes(), tmp_path / "img")
    assert dest.suffix == ".webp"
    with Image.open(dest) as saved:
        assert saved.format == "WEBP"


def test_non_image_bytes_rejected_regardless_of_claimed_extension(tmp_path):
    # A renamed executable/script — Pillow can't decode it into pixels no
    # matter what the (irrelevant, never passed in) filename claims.
    with pytest.raises(FlowImageError, match="not a valid"):
        validate_and_resave(b"#!/bin/sh\necho not an image\n", tmp_path / "img")


def test_svg_is_rejected():
    # SVG is not a raster format Pillow decodes into pixel data — content-
    # based validation must reject it even though some browsers/OSes treat
    # .svg as an "image".
    svg = b'<svg xmlns="http://www.w3.org/2000/svg"><rect width="1" height="1"/></svg>'
    with pytest.raises(FlowImageError):
        validate_and_resave(svg, None)  # dest never reached — validation fails first


def test_oversized_file_rejected_before_decoding(tmp_path):
    oversized = b"\x00" * (MAX_FILE_BYTES + 1)
    with pytest.raises(FlowImageError, match="exceeds"):
        validate_and_resave(oversized, tmp_path / "img")


def test_large_image_is_downscaled(tmp_path):
    huge = _png_bytes(size=(3000, 100))
    dest = validate_and_resave(huge, tmp_path / "img")
    with Image.open(dest) as saved:
        assert saved.width <= 1600


def test_transparent_png_saved_as_jpeg_source_does_not_crash(tmp_path):
    # RGBA content is fine for PNG (format stays PNG here — round-tripped
    # from an RGBA image, not forced to JPEG), just confirms no crash on
    # an alpha-channel image going through the pipeline.
    buf = io.BytesIO()
    Image.new("RGBA", (10, 10), (255, 0, 0, 128)).save(buf, format="PNG")
    dest = validate_and_resave(buf.getvalue(), tmp_path / "img")
    assert dest.suffix == ".png"
