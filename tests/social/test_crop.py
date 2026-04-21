"""Tests for flyer_generator.social.crop.

Per checker B1: direct-module imports only (no star imports).
"""

from __future__ import annotations

import io

import pytest
from PIL import Image

from flyer_generator.errors import SocialError
from flyer_generator.social.crop import (
    PLATFORM_CROP_SIZES,
    crop_all_platforms,
    crop_hero_for_platform,
    upscale_source_hero,
)


def _make_png(width: int, height: int, color: tuple[int, int, int] = (128, 128, 128)) -> bytes:
    img = Image.new("RGB", (width, height), color)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def test_platform_crop_sizes_has_nine_entries() -> None:
    # Per 19-RESEARCH.md §Aspect math lines 487-497 -- nine entries
    assert len(PLATFORM_CROP_SIZES) == 9
    assert PLATFORM_CROP_SIZES[("linkedin", "link_preview")] == (1200, 627)
    assert PLATFORM_CROP_SIZES[("instagram", "story")] == (1080, 1920)


def test_crop_hero_for_platform_returns_exact_dims() -> None:
    source = _make_png(2048, 2048)
    out = crop_hero_for_platform(source, 1200, 627)
    img = Image.open(io.BytesIO(out))
    assert img.size == (1200, 627)


def test_crop_hero_raises_on_garbage() -> None:
    with pytest.raises(SocialError):
        crop_hero_for_platform(b"not-an-image", 100, 100)


def test_upscale_source_hero_returns_2048() -> None:
    source = _make_png(1024, 1024)
    out = upscale_source_hero(source, target=(2048, 2048))
    img = Image.open(io.BytesIO(out))
    assert img.size == (2048, 2048)


def test_upscale_raises_on_50mp_overflow() -> None:
    source = _make_png(100, 100)
    with pytest.raises(SocialError):
        upscale_source_hero(source, target=(100000, 100000))


def test_crop_all_platforms_produces_dict() -> None:
    source = _make_png(2048, 2048)
    out = crop_all_platforms(
        source,
        [("linkedin", "link_preview"), ("instagram", "feed_square")],
    )
    assert set(out) == {("linkedin", "link_preview"), ("instagram", "feed_square")}
    img_li = Image.open(io.BytesIO(out[("linkedin", "link_preview")]))
    assert img_li.size == (1200, 627)
    img_ig = Image.open(io.BytesIO(out[("instagram", "feed_square")]))
    assert img_ig.size == (1080, 1080)


def test_crop_all_platforms_unknown_role_raises() -> None:
    source = _make_png(1024, 1024)
    with pytest.raises(SocialError):
        crop_all_platforms(source, [("linkedin", "nonsense")])  # type: ignore[list-item]
