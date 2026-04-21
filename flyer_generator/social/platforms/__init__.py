"""Platform rules registry -- populated at import time.

Callers should prefer :func:`validate_post` (dispatches by ``post.platform``)
and :func:`load_platform_rules` (returns a frozen :class:`PlatformRules`
instance) over importing the per-platform modules directly. The registry is a
module-level constant so it is effectively read-only from the caller side
(T-19-03-06 mitigation in the plan's threat model).
"""

from __future__ import annotations

from typing import Callable

from flyer_generator.errors import PlatformUnsupportedError
from flyer_generator.social.models import Platform, PlatformRules, Post, ValidationReport
from flyer_generator.social.platforms import facebook, instagram, linkedin, twitter

ValidateFn = Callable[..., ValidationReport]

PLATFORM_REGISTRY: dict[Platform, tuple[PlatformRules, ValidateFn]] = {
    "linkedin": (linkedin.RULES, linkedin.validate),
    "twitter": (twitter.RULES, twitter.validate),
    "instagram": (instagram.RULES, instagram.validate),
    "facebook": (facebook.RULES, facebook.validate),
}


def load_platform_rules(platform: str) -> PlatformRules:
    """Return the frozen PlatformRules for ``platform`` or raise PlatformUnsupportedError."""
    if platform not in PLATFORM_REGISTRY:
        raise PlatformUnsupportedError(
            f"unknown platform {platform!r}; known: {sorted(PLATFORM_REGISTRY)}"
        )
    return PLATFORM_REGISTRY[platform][0]  # type: ignore[index]


def validate_post(post: Post) -> ValidationReport:
    """Dispatch to the per-platform validate() for ``post.platform``."""
    platform = post.platform
    if platform not in PLATFORM_REGISTRY:
        raise PlatformUnsupportedError(
            f"unknown platform {platform!r}; known: {sorted(PLATFORM_REGISTRY)}"
        )
    _rules, fn = PLATFORM_REGISTRY[platform]  # type: ignore[index]
    return fn(post, _rules)


__all__ = [
    "PLATFORM_REGISTRY",
    "ValidateFn",
    "facebook",
    "instagram",
    "linkedin",
    "load_platform_rules",
    "twitter",
    "validate_post",
]
