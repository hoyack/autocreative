"""Test brand-kit storage: env-var resolution, slug validation, path containment.

All imports use direct-module paths (per checker B1): we import from
`flyer_generator.brand_kit.storage` and `flyer_generator.brand_kit.models`
directly, never from the package root (`flyer_generator.brand_kit`), so
Plans 01-06 never collide on `__init__.py`.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest

from flyer_generator.brand_kit.storage import (
    list_brand_kits,
    load_brand_kit,
    resolve_kit_dir,
    save_brand_kit,
)
from flyer_generator.config import Settings
from flyer_generator.errors import BrandKitError


# ---- Settings field resolution ------------------------------------------


def test_settings_default_brand_kits_dir() -> None:
    s = Settings()
    assert s.brand_kits_dir == Path(".brand-kits")


def test_settings_env_override(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("FLYER_BRAND_KITS_DIR", str(tmp_path))
    s = Settings()
    assert s.brand_kits_dir == tmp_path


# ---- resolve_kit_dir safety rails ---------------------------------------


def test_resolve_kit_dir_valid_slug(tmp_path: Path) -> None:
    p = resolve_kit_dir("my-kit", base_dir=tmp_path)
    assert p == tmp_path / "my-kit"


def test_resolve_kit_dir_rejects_uppercase(tmp_path: Path) -> None:
    with pytest.raises(BrandKitError):
        resolve_kit_dir("WithCaps", base_dir=tmp_path)


def test_resolve_kit_dir_rejects_traversal(tmp_path: Path) -> None:
    with pytest.raises(BrandKitError):
        resolve_kit_dir("../evil", base_dir=tmp_path)


def test_resolve_kit_dir_rejects_slash(tmp_path: Path) -> None:
    with pytest.raises(BrandKitError):
        resolve_kit_dir("a/b", base_dir=tmp_path)


# ---- list_brand_kits ----------------------------------------------------


def test_list_brand_kits_empty(tmp_path: Path) -> None:
    assert list_brand_kits(base_dir=tmp_path) == []


def test_list_brand_kits_sorted(tmp_path: Path) -> None:
    for name in ("charlie", "alpha", "bravo"):
        (tmp_path / name).mkdir()
        (tmp_path / name / "brand.json").write_text("{}")
    assert list_brand_kits(base_dir=tmp_path) == ["alpha", "bravo", "charlie"]


def test_list_brand_kits_ignores_bad_slugs(tmp_path: Path) -> None:
    (tmp_path / "Bad Name").mkdir()
    (tmp_path / "Bad Name" / "brand.json").write_text("{}")
    (tmp_path / "ok").mkdir()
    (tmp_path / "ok" / "brand.json").write_text("{}")
    assert list_brand_kits(base_dir=tmp_path) == ["ok"]


# ---- save_brand_kit / load_brand_kit ------------------------------------

# These tests exercise the round-trip path using a lazy import of BrandKit.
# If Plan 02 (models.py) has not landed yet, they SKIP via importorskip.


def _skip_if_no_models() -> None:
    pytest.importorskip("flyer_generator.brand_kit.models")


def test_save_and_load_round_trip(tmp_path: Path) -> None:
    _skip_if_no_models()
    from flyer_generator.brand_kit.models import BrandKit  # direct-module import

    kit = BrandKit(
        name="Test Brand",
        source_url="https://example.com",
        fetched_at=datetime(2026, 4, 20, tzinfo=timezone.utc),
        palette=None,
        typography=None,
        logos=[],
        voice=None,
        photography=None,
        source_artifacts=[],
        size_multiplier=1.0,
    )
    kit_dir = save_brand_kit(kit, "test-brand", base_dir=tmp_path)
    assert (kit_dir / "brand.json").is_file()
    assert (kit_dir / "logos").is_dir()
    assert (kit_dir / "source").is_dir()

    loaded = load_brand_kit("test-brand", base_dir=tmp_path)
    assert loaded.model_dump() == kit.model_dump()


def test_load_missing_raises(tmp_path: Path) -> None:
    _skip_if_no_models()
    with pytest.raises(FileNotFoundError):
        load_brand_kit("nonexistent", base_dir=tmp_path)
