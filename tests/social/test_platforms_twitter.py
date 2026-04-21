"""Per checker B1: direct-module imports only.

Covers Twitter: body > 280 -> TWITTER_TEXT_OVER; image_count=5 -> TWITTER_IMAGE_COUNT_OVER.
"""

from __future__ import annotations

import struct
import zlib

from flyer_generator.social.models import Post, PostCopy, ValidationReport
from flyer_generator.social.platforms import twitter
from flyer_generator.social.platforms import x as x_mod


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
        platform="twitter",
        intent="announcement",
        copy=PostCopy(title=None, body=body, cta=None, hashtags=hashtags or []),
        image_bytes=image,
        validation_report=ValidationReport(platform="twitter"),
        audit_summary="unknown",
    )


def test_twitter_pass_clean_post() -> None:
    img = _make_png(1200, 675)
    post = _make_post(body="Hi world!", hashtags=["#news", "#update"], image=img)
    report = twitter.validate(post)
    assert report.passed, f"unexpected issues: {report.issues}"


def test_twitter_body_over_280_errors() -> None:
    post = _make_post(body="x" * 350)
    report = twitter.validate(post)
    error_ids = [i.rule_id for i in report.errors()]
    assert "TWITTER_TEXT_OVER" in error_ids


def test_twitter_image_count_over_4_errors() -> None:
    img = _make_png(1200, 675)
    post = _make_post(body="x", image=img)
    report = twitter.validate(post, image_count=5)
    error_ids = [i.rule_id for i in report.errors()]
    assert "TWITTER_IMAGE_COUNT_OVER" in error_ids


def test_twitter_image_count_4_passes() -> None:
    img = _make_png(1200, 675)
    post = _make_post(body="x", image=img)
    report = twitter.validate(post, image_count=4)
    assert report.passed, f"unexpected issues: {report.issues}"


def test_twitter_rejects_wrong_aspect() -> None:
    img = _make_png(800, 600)
    post = _make_post(body="x", image=img)
    report = twitter.validate(post)
    error_ids = [i.rule_id for i in report.errors()]
    assert "TWITTER_IMAGE_ASPECT_MISMATCH" in error_ids


def test_twitter_x_alias_re_exports() -> None:
    # x is the post-2024 rebrand; must re-export twitter.RULES + validate
    assert x_mod.RULES is twitter.RULES
    assert x_mod.validate is twitter.validate
