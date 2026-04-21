"""Pillow-based helpers for campaign hero cropping.

Per 19-RESEARCH.md §Campaign Image Crop Strategy:

- Generate ONE source hero at the campaign's "largest requested" dimensions
  (via :func:`upscale_source_hero` when the model output is smaller than the
  widest consumer).
- Crop to each platform's target ``(width, height)`` via ``ImageOps.fit``
  center crop with LANCZOS resampling.

All functions are pure and stateless. Untrusted PNG bytes are guarded by the
Pillow ``verify()`` call and a 50 MP memory cap (T-19-04-01 / T-19-04-02).
"""

from __future__ import annotations

import io

from flyer_generator.errors import SocialError
from flyer_generator.social.models import Platform

# Per 19-PATTERNS.md §Shared Patterns: 50 MP cap on any decoded or target
# image to prevent decoder DoS. Matches brand_kit/audit.py convention.
_MAX_IMAGE_MP = 50_000_000

# Per 19-RESEARCH.md §Aspect math lines 487-497 -- nine entries
PLATFORM_CROP_SIZES: dict[tuple[Platform, str], tuple[int, int]] = {
    ("linkedin", "link_preview"): (1200, 627),
    ("linkedin", "feed_square"): (1200, 1200),
    ("twitter", "primary"): (1200, 675),
    ("instagram", "feed_square"): (1080, 1080),
    ("instagram", "feed_portrait"): (1080, 1350),
    ("instagram", "story"): (1080, 1920),
    ("facebook", "link_preview"): (1200, 630),
    ("facebook", "feed_square"): (1080, 1080),
    ("facebook", "feed_portrait"): (1080, 1350),
}


def crop_hero_for_platform(
    source_bytes: bytes,
    target_w: int,
    target_h: int,
) -> bytes:
    """Center-crop + resize source bytes to ``(target_w, target_h)`` via LANCZOS.

    Args:
        source_bytes: PNG/JPEG bytes of the source hero image.
        target_w: Target width in pixels.
        target_h: Target height in pixels.

    Returns:
        PNG bytes of a ``(target_w, target_h)`` image.

    Raises:
        SocialError: when ``source_bytes`` cannot be decoded, when the source
            image exceeds the 50 MP cap, or when the target dimensions would
            allocate over 50 MP.
    """
    from PIL import Image, ImageOps  # noqa: PLC0415 -- lazy import

    try:
        probe = Image.open(io.BytesIO(source_bytes))
        probe.verify()
    except Exception as err:  # noqa: BLE001 -- untrusted bytes (T-19-04-01)
        raise SocialError(
            "could not open source hero as image", error=str(err)
        ) from err
    # Re-open after verify() (verify consumes the stream state)
    source = Image.open(io.BytesIO(source_bytes)).convert("RGB")
    w, h = source.size
    if w * h > _MAX_IMAGE_MP:
        raise SocialError("source hero exceeds 50 MP cap", width=w, height=h)
    if target_w * target_h > _MAX_IMAGE_MP:
        raise SocialError(
            "target size exceeds 50 MP cap",
            target_w=target_w,
            target_h=target_h,
        )
    cropped = ImageOps.fit(
        source,
        size=(target_w, target_h),
        method=Image.Resampling.LANCZOS,
        centering=(0.5, 0.5),
    )
    buf = io.BytesIO()
    cropped.save(buf, format="PNG")
    return buf.getvalue()


def upscale_source_hero(
    source_bytes: bytes,
    target: tuple[int, int] = (2048, 2048),
) -> bytes:
    """Upscale source to ``target`` dimensions via Pillow LANCZOS.

    Per 19-RESEARCH.md §Campaign Image Crop Strategy §Source hero dimension:
    no ComfyCloud workflow emits 2048 natively; upscale via Pillow LANCZOS
    from the native 1024-ish output is the recommended path (Option 1 in
    the research).

    Args:
        source_bytes: PNG/JPEG bytes of the source hero image.
        target: ``(width, height)`` to upscale to.

    Returns:
        PNG bytes at the target dimensions.

    Raises:
        SocialError: when the source cannot be decoded, when the source or
            target exceeds the 50 MP cap.
    """
    from PIL import Image  # noqa: PLC0415

    target_w, target_h = target
    if target_w * target_h > _MAX_IMAGE_MP:
        raise SocialError(
            "target size exceeds 50 MP cap",
            target_w=target_w,
            target_h=target_h,
        )
    try:
        source = Image.open(io.BytesIO(source_bytes)).convert("RGB")
    except Exception as err:  # noqa: BLE001 -- untrusted bytes (T-19-04-02)
        raise SocialError(
            "could not open source hero for upscale", error=str(err)
        ) from err
    w, h = source.size
    if w * h > _MAX_IMAGE_MP:
        raise SocialError("source hero exceeds 50 MP cap", width=w, height=h)
    upscaled = source.resize((target_w, target_h), Image.Resampling.LANCZOS)
    buf = io.BytesIO()
    upscaled.save(buf, format="PNG")
    return buf.getvalue()


def crop_all_platforms(
    source_bytes: bytes,
    platform_roles: list[tuple[Platform, str]],
) -> dict[tuple[Platform, str], bytes]:
    """Produce a dict of ``{(platform, role): PNG bytes}`` for each requested slot.

    Args:
        source_bytes: Source hero PNG bytes (typically from
            :func:`upscale_source_hero`).
        platform_roles: List of ``(platform, role)`` keys to emit; each must
            exist in :data:`PLATFORM_CROP_SIZES`.

    Returns:
        Mapping keyed by ``(platform, role)`` whose values are PNG bytes at
        the correct dimensions for that slot.

    Raises:
        SocialError: when any ``(platform, role)`` is not in
            :data:`PLATFORM_CROP_SIZES`, or when cropping fails per
            :func:`crop_hero_for_platform`.
    """
    out: dict[tuple[Platform, str], bytes] = {}
    for key in platform_roles:
        if key not in PLATFORM_CROP_SIZES:
            raise SocialError(
                f"unknown platform/role {key!r}; known: {sorted(PLATFORM_CROP_SIZES)}",
            )
        w, h = PLATFORM_CROP_SIZES[key]
        out[key] = crop_hero_for_platform(source_bytes, w, h)
    return out


# Short-form alias used by the orchestrator/success-criteria checks.
# Prefer :func:`crop_hero_for_platform` in new call sites.
crop_to_aspect = crop_hero_for_platform
