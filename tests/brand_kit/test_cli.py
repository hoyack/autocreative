"""Brand-kit CLI tests via typer's CliRunner."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest
from typer.testing import CliRunner

from flyer_generator.brand_kit.__main__ import app
from flyer_generator.brand_kit.models import BrandKit

runner = CliRunner(mix_stderr=False)


# ---- list ---------------------------------------------------------------


def test_list_empty(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("FLYER_BRAND_KITS_DIR", str(tmp_path))
    result = runner.invoke(app, ["list"])
    assert result.exit_code == 0
    assert result.stdout.strip() == ""


def test_list_three_kits_sorted(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("FLYER_BRAND_KITS_DIR", str(tmp_path))
    for name in ("charlie", "alpha", "bravo"):
        (tmp_path / name).mkdir()
        (tmp_path / name / "brand.json").write_text("{}")
    result = runner.invoke(app, ["list"])
    assert result.exit_code == 0
    lines = [ln for ln in result.stdout.strip().splitlines() if ln]
    assert lines == ["alpha", "bravo", "charlie"]


# ---- show ---------------------------------------------------------------


def test_show_missing_exits_nonzero(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("FLYER_BRAND_KITS_DIR", str(tmp_path))
    result = runner.invoke(app, ["show", "missing"])
    assert result.exit_code != 0


def test_show_valid_prints_json(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("FLYER_BRAND_KITS_DIR", str(tmp_path))
    kit = BrandKit(
        name="Test",
        source_url="https://example.com",
        fetched_at=datetime(2026, 4, 20, tzinfo=timezone.utc),
    )
    kit_dir = tmp_path / "test-kit"
    kit_dir.mkdir()
    (kit_dir / "brand.json").write_text(kit.model_dump_json(indent=2))

    result = runner.invoke(app, ["show", "test-kit"])
    assert result.exit_code == 0
    parsed = json.loads(result.stdout)
    assert parsed["name"] == "Test"


# ---- fetch --------------------------------------------------------------


def test_fetch_happy_path(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("FLYER_BRAND_KITS_DIR", str(tmp_path))

    called: dict[str, object] = {}

    async def fake_fetch(url: str, slug: str, **_kwargs) -> BrandKit:
        called["url"] = url
        called["slug"] = slug
        return BrandKit(
            name=slug,
            source_url=url,
            fetched_at=datetime(2026, 4, 20, tzinfo=timezone.utc),
        )

    monkeypatch.setattr(
        "flyer_generator.brand_kit.__main__.fetch_brand_kit", fake_fetch
    )

    result = runner.invoke(
        app, ["fetch", "https://example.com", "--slug", "test"]
    )
    assert result.exit_code == 0
    assert called["url"] == "https://example.com"
    assert called["slug"] == "test"


def test_fetch_ssrf_exits_nonzero(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("FLYER_BRAND_KITS_DIR", str(tmp_path))
    result = runner.invoke(
        app, ["fetch", "http://127.0.0.1/", "--slug", "ssrf"]
    )
    assert result.exit_code != 0
    combined = (result.stdout + (result.stderr or "")).lower()
    assert (
        "ssrf" in combined
        or "blocked" in combined
        or "loopback" in combined
        or "ip " in combined
        or "reason" in combined
        or "private" in combined
    )


def test_fetch_bad_slug_exits_nonzero(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("FLYER_BRAND_KITS_DIR", str(tmp_path))
    result = runner.invoke(
        app, ["fetch", "https://example.com", "--slug", "BadSlug!"]
    )
    assert result.exit_code != 0
