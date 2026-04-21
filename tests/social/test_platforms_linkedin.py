"""Per checker B1: direct-module imports only.

Covers the 19-RESEARCH.md §Testing Matrix row for LinkedIn: body-over-hard-cap,
image-bytes-over, accepted 1200x1200 secondary aspect, rejected 800x600.
"""

from __future__ import annotations

import struct
import zlib

from flyer_generator.social.models import Post, PostCopy, ValidationReport
from flyer_generator.social.platforms import linkedin


def _make_png(width: int, height: int) -> bytes:
    """Return a valid minimal PNG of given dimensions (uniform gray 8-bit RGB)."""

    def chunk(tag: bytes, data: bytes) -> bytes:
        return (
            struct.pack(">I", len(data))
            + tag
            + data
            + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
        )

    sig = b"\x89PNG\r\n\x1a\n"
    ihdr = chunk(
        b"IHDR",
        struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0),  # 8-bit RGB
    )
    raw = b""
    row = b"\x00" + b"\x00\x00\x00" * width  # filter byte + RGB zeros
    for _ in range(height):
        raw += row
    idat = chunk(b"IDAT", zlib.compress(raw))
    iend = chunk(b"IEND", b"")
    return sig + ihdr + idat + iend


def _make_post(
    body: str = "x",
    hashtags: list[str] | None = None,
    image: bytes | None = None,
) -> Post:
    return Post(
        platform="linkedin",
        intent="value-prop",
        copy=PostCopy(title="T", body=body, cta="C", hashtags=hashtags or []),
        image_bytes=image,
        validation_report=ValidationReport(platform="linkedin"),
        audit_summary="unknown",
    )


def test_linkedin_pass_clean_post() -> None:
    img = _make_png(1200, 627)
    post = _make_post(body="x" * 2000, hashtags=["#abc", "#defg", "#hijk", "#lmno"], image=img)
    report = linkedin.validate(post)
    assert report.passed is True, f"unexpected issues: {report.issues}"


def test_linkedin_body_over_hard_cap_errors() -> None:
    post = _make_post(body="x" * 3500)
    report = linkedin.validate(post)
    assert not report.passed
    error_ids = [i.rule_id for i in report.errors()]
    assert "LINKEDIN_BODY_OVER" in error_ids


def test_linkedin_image_bytes_over_errors() -> None:
    img = _make_png(1200, 627)
    # Pad to > 5 MB by appending junk after IEND; Pillow ignores trailing bytes.
    padded = img + b"\x00" * (6 * 1024 * 1024)
    post = _make_post(body="x", hashtags=[], image=padded)
    report = linkedin.validate(post)
    error_ids = [i.rule_id for i in report.errors()]
    assert "LINKEDIN_IMAGE_BYTES_OVER" in error_ids


def test_linkedin_accepts_1200x1200_secondary_aspect() -> None:
    img = _make_png(1200, 1200)
    post = _make_post(body="x", image=img)
    report = linkedin.validate(post)
    assert report.passed
    assert not any(i.rule_id == "LINKEDIN_IMAGE_ASPECT_MISMATCH" for i in report.issues)


def test_linkedin_rejects_wrong_aspect() -> None:
    img = _make_png(800, 600)
    post = _make_post(body="x", image=img)
    report = linkedin.validate(post)
    error_ids = [i.rule_id for i in report.errors()]
    assert "LINKEDIN_IMAGE_ASPECT_MISMATCH" in error_ids
