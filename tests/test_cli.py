"""Tests for the CLI entrypoint (flyer_generator/__main__.py)."""

from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from flyer_generator.__main__ import app

runner = CliRunner()

# A valid EventInput as a dict for JSON fixtures
_SAMPLE_EVENT = {
    "title": "Test Event",
    "date": "Saturday, May 2, 2026",
    "time": "9:00 AM - 12:00 PM",
    "location_name": "Test Venue",
    "location_address": "123 Test St, Test City, TX 78205",
    "fees": "FREE",
    "org": "Test Org",
    "style_concept": "community outdoor event, park setting",
    "style_preset": "photorealistic",
    "color_accent": "#F59E0B",
}

# All required CLI args matching the sample event
_REQUIRED_ARGS = [
    "--title", "Test Event",
    "--date", "Saturday, May 2, 2026",
    "--time", "9:00 AM - 12:00 PM",
    "--venue", "Test Venue",
    "--address", "123 Test St, Test City, TX 78205",
    "--fees", "FREE",
    "--org", "Test Org",
    "--concept", "community outdoor event, park setting",
    "--preset", "photorealistic",
]

_ALL_PRESET_NAMES = [
    "anime",
    "photorealistic",
    "retro_poster",
    "scifi",
    "watercolor",
    "western_cartoon",
]


def test_help() -> None:
    """--help shows usage with all expected flags."""
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "--title" in result.output
    assert "--preset" in result.output
    assert "--event-json" in result.output
    assert "--list-presets" in result.output
    assert "--dry-run" in result.output
    assert "--max-attempts" in result.output


def test_list_presets() -> None:
    """--list-presets prints all 6 preset names and exits."""
    result = runner.invoke(app, ["--list-presets"])
    assert result.exit_code == 0
    for name in _ALL_PRESET_NAMES:
        assert name in result.output


def test_dry_run() -> None:
    """--dry-run with required args prints prompt text without API calls."""
    result = runner.invoke(app, [*_REQUIRED_ARGS, "--dry-run"])
    assert result.exit_code == 0
    assert "Positive Prompt" in result.output
    assert "Negative Prompt" in result.output
    # Should contain preset-derived content
    assert "cinematic" in result.output.lower() or "photograph" in result.output.lower()


def test_event_json(tmp_path: Path) -> None:
    """--event-json loads event from file, combined with --dry-run."""
    json_file = tmp_path / "event.json"
    json_file.write_text(json.dumps(_SAMPLE_EVENT), encoding="utf-8")

    result = runner.invoke(app, ["--event-json", str(json_file), "--dry-run"])
    assert result.exit_code == 0
    assert "Positive Prompt" in result.output


def test_event_json_invalid(tmp_path: Path) -> None:
    """--event-json with invalid JSON gives a clear error."""
    json_file = tmp_path / "bad.json"
    json_file.write_text('{"title": "missing fields"}', encoding="utf-8")

    result = runner.invoke(app, ["--event-json", str(json_file), "--dry-run"])
    assert result.exit_code == 1
    assert "Error" in result.output or "error" in result.output


def test_missing_required_args() -> None:
    """Invoking with no args (and no --list-presets/--event-json) errors."""
    result = runner.invoke(app, [])
    assert result.exit_code == 1
    assert "missing required" in result.output.lower() or "error" in result.output.lower()


def test_max_attempts_flag() -> None:
    """--max-attempts parses correctly (verified via --dry-run, no API call needed)."""
    result = runner.invoke(app, [*_REQUIRED_ARGS, "--dry-run", "--max-attempts", "5"])
    assert result.exit_code == 0
    assert "Positive Prompt" in result.output
