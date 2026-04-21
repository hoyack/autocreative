"""Test BrandKitError hierarchy and typed-context kwargs."""

from __future__ import annotations

import pytest

from flyer_generator.errors import (
    BrandKitAuditError,
    BrandKitContrastError,
    BrandKitError,
    BrandKitScrapeError,
    FlyerGeneratorError,
)


def test_brand_kit_error_is_flyer_error() -> None:
    assert issubclass(BrandKitError, FlyerGeneratorError)
    assert issubclass(BrandKitScrapeError, BrandKitError)
    assert issubclass(BrandKitContrastError, BrandKitError)
    assert issubclass(BrandKitAuditError, BrandKitError)


def test_scrape_error_round_trips_context() -> None:
    err = BrandKitScrapeError("boom", trace_id="abc123", url="https://x.example")
    assert err.trace_id == "abc123"
    assert err.context == {"url": "https://x.example"}
    assert str(err) == "boom"


def test_audit_error_has_cycles_field() -> None:
    err = BrandKitAuditError("loop exhausted", cycles=3, remaining_issues=["i1", "i2"])
    assert err.cycles == 3
    assert err.remaining_issues == ["i1", "i2"]


def test_can_raise_and_catch_as_base() -> None:
    with pytest.raises(BrandKitError):
        raise BrandKitContrastError("no AA")
