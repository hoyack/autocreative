"""Integration tests for --brand-kit in the schema_renderer CLI.

Plumbing only -- no real image generation or network calls. Must run offline.
W11: tests do NOT pass the svg-writing opt-out flag in their invocations. The
real flag exists in flyer_generator/brochure/schema_renderer/__main__.py:64-67;
tests rely on its default plus tmpdir. Assertions cover exit code, stdout,
and stderr only."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest
from typer.testing import CliRunner

from flyer_generator.brand_kit.models import (
    BrandKit,
    BrandPalette,
    ColorUsage,
)
from flyer_generator.brand_kit.storage import save_brand_kit
from flyer_generator.brochure.schema_renderer.__main__ import app

runner = CliRunner()


@pytest.fixture
def kits_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    """Set both FLYER_BRAND_KITS_DIR and FLYER_BRAND_KITS_ALLOW_SYSTEM=1."""
    monkeypatch.setenv("FLYER_BRAND_KITS_DIR", str(tmp_path))
    monkeypatch.setenv("FLYER_BRAND_KITS_ALLOW_SYSTEM", "1")
    return tmp_path


def _write_kit(
    tmp_path: Path,
    slug: str,
    *,
    primary: str = "#AABBCC",
) -> Path:
    kit = BrandKit(
        name="Test",
        source_url="https://example.com",
        fetched_at=datetime(2026, 4, 20, tzinfo=timezone.utc),
        palette=BrandPalette(
            primary=ColorUsage(hex=primary),
            secondary=ColorUsage(hex="#DDEEFF"),
            accent=ColorUsage(hex="#112233"),
            neutral_dark=ColorUsage(hex="#1A1A1A"),
            neutral_light=ColorUsage(hex="#FAFAF7"),
        ),
    )
    save_brand_kit(kit, slug, base_dir=tmp_path)
    return tmp_path / slug


def _write_content_json(path: Path) -> Path:
    payload = {
        "title": "Test Title",
        "subtitle": "Subtitle",
        "tagline": "Tagline",
        "org": "Acme",
        "sections": [
            {
                "heading": "Heading 1",
                "lead_paragraph": "Lead text.",
                "body_paragraphs": ["Para one."],
                "bullets": ["A", "B"],
            }
        ],
    }
    path.write_text(json.dumps(payload))
    return path


def test_brand_kit_applied_changes_palette(kits_env: Path) -> None:
    _write_kit(kits_env, "bk")
    content_path = _write_content_json(kits_env / "content.json")
    out_dir = kits_env / "out"

    result = runner.invoke(
        app,
        [
            "--template", "editorial_classic",
            "--content", str(content_path),
            "--output", str(out_dir),
            "--brand-kit", "bk",
        ],
    )
    assert "Applied brand kit: bk" in result.stdout, result.stdout
    assert result.exit_code == 0, (result.stderr or "") + result.stdout


def test_brand_kit_overrides_color_accent(kits_env: Path) -> None:
    _write_kit(kits_env, "bk")
    content_path = _write_content_json(kits_env / "content.json")
    out_dir = kits_env / "out"

    result = runner.invoke(
        app,
        [
            "--template", "editorial_classic",
            "--content", str(content_path),
            "--output", str(out_dir),
            "--brand-kit", "bk",
            "--color-accent", "#FF00FF",
        ],
    )
    stderr = result.stderr or ""
    assert "overrides --color-accent" in stderr
    assert result.exit_code == 0, stderr + result.stdout


def test_brand_kit_missing_exits_2(kits_env: Path) -> None:
    content_path = _write_content_json(kits_env / "content.json")
    out_dir = kits_env / "out"

    result = runner.invoke(
        app,
        [
            "--template", "editorial_classic",
            "--content", str(content_path),
            "--output", str(out_dir),
            "--brand-kit", "nonexistent",
        ],
    )
    assert result.exit_code == 2
    err = result.stderr or ""
    assert "not found" in err or "nonexistent" in err


def test_explicit_logo_overrides_brand_kit(kits_env: Path) -> None:
    kit_dir = _write_kit(kits_env, "bk")
    (kit_dir / "logos").mkdir(exist_ok=True)
    (kit_dir / "logos" / "p.png").write_bytes(b"kit-logo-bytes")
    explicit_logo = kits_env / "explicit.png"
    from PIL import Image
    Image.new("RGB", (32, 32), (255, 0, 0)).save(explicit_logo)

    content_path = _write_content_json(kits_env / "content.json")
    out_dir = kits_env / "out"

    result = runner.invoke(
        app,
        [
            "--template", "editorial_classic",
            "--content", str(content_path),
            "--output", str(out_dir),
            "--brand-kit", "bk",
            "--logo", str(explicit_logo),
        ],
    )
    assert "Loaded logo:" in result.stdout
    assert "Using brand-kit logo" not in result.stdout
    assert result.exit_code == 0, result.stderr or ""
