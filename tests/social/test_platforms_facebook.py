"""Per checker B1: direct-module imports only.

Covers Facebook: body > 500 (recommended) -> FACEBOOK_BODY_LONG warn, pass True;
body > 63206 (system cap) -> FACEBOOK_BODY_OVER error, pass False.
Also tests registry via load_platform_rules + validate_post.
"""

from __future__ import annotations

import struct
import zlib

import pytest

from flyer_generator.errors import PlatformUnsupportedError
from flyer_generator.social.models import Post, PostCopy, ValidationReport
from flyer_generator.social.platforms import (
    PLATFORM_REGISTRY,
    facebook,
    load_platform_rules,
    validate_post,
)


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
    platform: str = "facebook",
) -> Post:
    return Post(
        platform=platform,  # type: ignore[arg-type]
        intent="announcement",
        copy=PostCopy(title=None, body=body, cta=None, hashtags=hashtags or []),
        image_bytes=image,
        validation_report=ValidationReport(platform=platform),  # type: ignore[arg-type]
        audit_summary="unknown",
    )


def test_facebook_short_body_passes_no_warn() -> None:
    img = _make_png(1200, 630)
    post = _make_post(body="short post", image=img)
    report = facebook.validate(post)
    assert report.passed
    assert not any(i.rule_id == "FACEBOOK_BODY_LONG" for i in report.issues)


def test_facebook_body_1000_warn_but_passes() -> None:
    post = _make_post(body="x" * 1000)
    report = facebook.validate(post)
    assert report.passed is True  # hard cap not hit
    warn_ids = [i.rule_id for i in report.warnings()]
    assert "FACEBOOK_BODY_LONG" in warn_ids


def test_facebook_body_over_system_cap_errors() -> None:
    post = _make_post(body="x" * (63206 + 10))
    report = facebook.validate(post)
    error_ids = [i.rule_id for i in report.errors()]
    assert "FACEBOOK_BODY_OVER" in error_ids


def test_facebook_accepts_1080x1080_square() -> None:
    img = _make_png(1080, 1080)
    post = _make_post(body="x", image=img)
    report = facebook.validate(post)
    assert report.passed
    assert not any(i.rule_id == "FACEBOOK_IMAGE_ASPECT_MISMATCH" for i in report.issues)


def test_platform_registry_keys() -> None:
    assert set(PLATFORM_REGISTRY) == {"linkedin", "twitter", "instagram", "facebook"}


def test_load_platform_rules_linkedin() -> None:
    from flyer_generator.social.platforms import linkedin

    assert load_platform_rules("linkedin") is linkedin.RULES


def test_load_platform_rules_unknown_raises() -> None:
    with pytest.raises(PlatformUnsupportedError):
        load_platform_rules("myspace")


def test_validate_post_dispatches_to_facebook() -> None:
    post = _make_post(body="short")
    report = validate_post(post)
    assert report.platform == "facebook"
    assert report.passed
