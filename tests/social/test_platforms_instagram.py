"""Per checker B1: direct-module imports only.

Covers Instagram: 31 hashtags -> INSTAGRAM_HASHTAG_COUNT_OVER; URL in caption ->
INSTAGRAM_LINK_IN_CAPTION at WARN severity but report.passed stays True
(per 19-RESEARCH.md §Open Risks #1).
"""

from __future__ import annotations

import struct
import zlib

from flyer_generator.social.models import Post, PostCopy, ValidationReport
from flyer_generator.social.platforms import instagram


def _make_png(width: int, height: int) -> bytes:
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
        struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0),
    )
    raw = b""
    row = b"\x00" + b"\x00\x00\x00" * width
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
        platform="instagram",
        intent="value-prop",
        copy=PostCopy(title=None, body=body, cta=None, hashtags=hashtags or []),
        image_bytes=image,
        validation_report=ValidationReport(platform="instagram"),
        audit_summary="unknown",
    )


def test_instagram_pass_clean_post() -> None:
    img = _make_png(1080, 1080)
    post = _make_post(body="nice caption", hashtags=["#abcd", "#efgh"], image=img)
    report = instagram.validate(post)
    assert report.passed, f"unexpected issues: {report.issues}"


def test_instagram_caption_over_2200_errors() -> None:
    post = _make_post(body="x" * 2500)
    report = instagram.validate(post)
    error_ids = [i.rule_id for i in report.errors()]
    assert "INSTAGRAM_CAPTION_OVER" in error_ids


def test_instagram_31_hashtags_errors() -> None:
    tags = [f"#tag{i:02d}" for i in range(31)]
    post = _make_post(body="x", hashtags=tags)
    report = instagram.validate(post)
    error_ids = [i.rule_id for i in report.errors()]
    assert "INSTAGRAM_HASHTAG_COUNT_OVER" in error_ids
    # Generic primitive's rule_id must have been re-mapped to platform-specific
    assert "HASHTAG_COUNT_CAP" not in error_ids


def test_instagram_url_in_caption_is_warn_not_error() -> None:
    post = _make_post(body="Check out https://example.com now!")
    report = instagram.validate(post)
    assert report.passed is True  # warn only, not error
    warn_ids = [i.rule_id for i in report.warnings()]
    assert "INSTAGRAM_LINK_IN_CAPTION" in warn_ids


def test_instagram_accepts_1080x1350_portrait() -> None:
    img = _make_png(1080, 1350)
    post = _make_post(body="x", image=img)
    report = instagram.validate(post)
    assert report.passed
    assert not any(i.rule_id == "INSTAGRAM_IMAGE_ASPECT_MISMATCH" for i in report.issues)


def test_instagram_accepts_1080x1920_story() -> None:
    img = _make_png(1080, 1920)
    post = _make_post(body="x", image=img)
    report = instagram.validate(post)
    assert report.passed
    assert not any(i.rule_id == "INSTAGRAM_IMAGE_ASPECT_MISMATCH" for i in report.issues)
