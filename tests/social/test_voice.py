"""Per Phase 18 checker B1: imports use direct-module paths so this file
never imports from the package-root __init__.py (which does not yet exist
for flyer_generator.social)."""

from __future__ import annotations

import pytest

from flyer_generator.errors import BrandKitError, BrandVoiceViolationError, FlyerGeneratorError


def test_brand_voice_violation_error_is_brand_kit_error_subclass() -> None:
    err = BrandVoiceViolationError("x")
    assert isinstance(err, BrandKitError)
    assert isinstance(err, FlyerGeneratorError)


def test_brand_voice_violation_error_populates_context_fields() -> None:
    err = BrandVoiceViolationError(
        "banned word used",
        banned_matches=["ai", "ml"],
        keys=["copy.body", "copy.title"],
    )
    assert err.banned_matches == ["ai", "ml"]
    assert err.keys == ["copy.body", "copy.title"]


def test_brand_voice_violation_error_defaults_empty_lists() -> None:
    err = BrandVoiceViolationError("msg")
    assert err.banned_matches == []
    assert err.keys == []
