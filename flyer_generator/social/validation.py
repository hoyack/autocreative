"""Shared validation primitives for platform-specific validators.

All check_* helpers are pure functions: they take the data to check and
identifiers for error reporting, and return either ``None`` / ``[]`` for a
pass or one-or-more :class:`~flyer_generator.social.models.ValidationIssue`
objects for failures. Platform-specific ``validate()`` functions compose them
and re-map generic ``rule_id`` values into platform-namespaced ones when
needed (e.g. ``HASHTAG_COUNT_CAP`` -> ``INSTAGRAM_HASHTAG_COUNT_OVER``).

``_pillow_dims`` is the single decoding site for untrusted PNG/JPEG bytes;
it enforces a 50 megapixel cap (same as brand_kit/audit.py) to protect
against decompression bombs and raises :class:`SocialError` on malformed
input or over-cap dimensions.
"""

from __future__ import annotations

import io
import re
from typing import TYPE_CHECKING

from flyer_generator.errors import SocialError
from flyer_generator.social.models import (
    ImageAspect,
    ValidationIssue,
)

if TYPE_CHECKING:  # pragma: no cover
    pass

_MAX_IMAGE_MP = 50_000_000  # 50 MP cap per brand_kit/audit.py
_URL_RE = re.compile(r"https?://\S+", re.IGNORECASE)
_HASHTAG_VALID_RE = re.compile(r"^#[A-Za-z0-9_]+$")


def check_char_limit(
    text: str,
    max_chars: int,
    field: str,
    rule_id: str,
) -> ValidationIssue | None:
    """Return an error-severity issue when ``len(text) > max_chars``, else None."""
    n = len(text)
    if n > max_chars:
        return ValidationIssue(
            severity="error",
            rule_id=rule_id,
            message=f"{field} is {n} chars, exceeds platform max {max_chars}",
            field=field,
            actual=n,
            expected=max_chars,
        )
    return None


def check_hashtag_count(
    tags: list[str],
    hard_max: int | None,
    field: str,
) -> list[ValidationIssue]:
    """Validate hashtag list: hard cap + per-tag format/chars/length.

    ``hard_max=None`` means the platform has no hard cap (warn is audit's job).
    Format/character rules apply regardless of hard cap.
    """
    issues: list[ValidationIssue] = []
    if hard_max is not None and len(tags) > hard_max:
        issues.append(
            ValidationIssue(
                severity="error",
                rule_id="HASHTAG_COUNT_CAP",
                message=f"{len(tags)} hashtags exceeds platform hard cap {hard_max}",
                field=field,
                actual=len(tags),
                expected=hard_max,
            )
        )
    for i, t in enumerate(tags):
        if not t.startswith("#"):
            issues.append(
                ValidationIssue(
                    severity="error",
                    rule_id="HASHTAG_FORMAT",
                    message=f"hashtag[{i}] {t!r} does not start with '#'",
                    field=f"{field}[{i}]",
                )
            )
            continue
        if not _HASHTAG_VALID_RE.match(t):
            issues.append(
                ValidationIssue(
                    severity="error",
                    rule_id="HASHTAG_CHARS",
                    message=f"hashtag[{i}] {t!r} has invalid characters",
                    field=f"{field}[{i}]",
                )
            )
            continue
        if len(t) > 25 or len(t) < 4:
            issues.append(
                ValidationIssue(
                    severity="warn",
                    rule_id="HASHTAG_LENGTH",
                    message=f"hashtag[{i}] {t!r} is {len(t)} chars (prefer 4-24)",
                    field=f"{field}[{i}]",
                )
            )
    return issues


def check_image_bytes(
    nbytes: int,
    max_bytes: int,
    recommended_max: int,
    rule_id_error: str = "IMAGE_BYTES_OVER",
    rule_id_warn: str = "IMAGE_BYTES_LARGE",
) -> list[ValidationIssue]:
    """Error on >max_bytes; warn on >recommended_max (platform may recompress)."""
    issues: list[ValidationIssue] = []
    if nbytes > max_bytes:
        issues.append(
            ValidationIssue(
                severity="error",
                rule_id=rule_id_error,
                message=f"image is {nbytes} bytes, exceeds platform max {max_bytes}",
                field="image.bytes",
                actual=nbytes,
                expected=max_bytes,
            )
        )
    elif nbytes > recommended_max:
        issues.append(
            ValidationIssue(
                severity="warn",
                rule_id=rule_id_warn,
                message=(
                    f"image is {nbytes} bytes, above recommended {recommended_max} "
                    f"-- may be recompressed by platform"
                ),
                field="image.bytes",
                actual=nbytes,
                expected=recommended_max,
            )
        )
    return issues


def check_image_aspect(
    actual_w: int,
    actual_h: int,
    allowed: tuple[ImageAspect, ...],
    tolerance: float = 0.02,
    rule_id: str = "IMAGE_ASPECT_MISMATCH",
) -> list[ValidationIssue]:
    """Return an error-severity issue when the aspect is outside tolerance of every allowed."""
    if not allowed:
        return []
    actual_ratio = actual_w / actual_h if actual_h else 0.0
    for spec in allowed:
        if abs(actual_ratio - spec.aspect_ratio) / spec.aspect_ratio <= tolerance:
            return []
    expected_ratios = ", ".join(
        f"{a.width}x{a.height} ({a.role})" for a in allowed
    )
    return [
        ValidationIssue(
            severity="error",
            rule_id=rule_id,
            message=(
                f"image {actual_w}x{actual_h} (ratio {actual_ratio:.3f}) "
                f"does not match any allowed: {expected_ratios}"
            ),
            field="image.aspect",
            actual=f"{actual_w}x{actual_h}",
            expected=expected_ratios,
        )
    ]


def check_image_count(
    count: int,
    max_count: int,
    rule_id: str = "IMAGE_COUNT_OVER",
) -> list[ValidationIssue]:
    """Return an error-severity issue when ``count > max_count``."""
    if count > max_count:
        return [
            ValidationIssue(
                severity="error",
                rule_id=rule_id,
                message=f"{count} images exceeds platform max {max_count}",
                field="images",
                actual=count,
                expected=max_count,
            )
        ]
    return []


def check_no_urls_in_text(
    text: str,
    rule_id: str,
    severity: str = "warn",
) -> list[ValidationIssue]:
    """Return an issue when the text contains one or more ``https?://`` URLs."""
    matches = _URL_RE.findall(text)
    if not matches:
        return []
    return [
        ValidationIssue(
            severity=severity,  # type: ignore[arg-type]
            rule_id=rule_id,
            message=(
                f"caption contains URL(s); platform strips links from caption: {matches}"
            ),
            field="copy.body",
            actual=matches,
        )
    ]


def _pillow_dims(image_bytes: bytes) -> tuple[int, int]:
    """Return (width, height). Raises SocialError on invalid image or >50 MP.

    Lazy-imports Pillow to keep the validation module cheap when only the
    text-side primitives are used. ``Image.verify()`` consumes the stream,
    so we reopen for the dimensions read.
    """
    from PIL import Image  # noqa: PLC0415

    try:
        img = Image.open(io.BytesIO(image_bytes))
        img.verify()  # verify() consumes the stream; reopen for dims
    except Exception as err:  # noqa: BLE001 -- untrusted bytes
        raise SocialError(
            "could not open image as PNG/JPEG", error=str(err)
        ) from err
    img = Image.open(io.BytesIO(image_bytes))
    w, h = img.size
    if w * h > _MAX_IMAGE_MP:
        raise SocialError(
            "image exceeds 50 MP cap", width=w, height=h
        )
    return (w, h)


# Convenience re-export so callers can do
# ``from flyer_generator.social.validation import validate_post``
# without reaching into the platforms package (Plan 19-03 success_criteria).
def validate_post(post: "Post") -> "ValidationReport":  # type: ignore[name-defined]  # noqa: F821
    """Dispatch ``post`` to its per-platform validator via the platforms registry.

    Thin wrapper over :func:`flyer_generator.social.platforms.validate_post`.
    Kept here so that the shared primitives module exposes the public API
    alongside the ``check_*`` helpers.
    """
    from flyer_generator.social.platforms import validate_post as _dispatch  # noqa: PLC0415

    return _dispatch(post)
