"""Per checker B1: direct-module imports only.

Asserts the five-command typer CLI in flyer_generator/social/__main__.py
works without any external services (no brand kit I/O, no ComfyCloud, no LLM).
"""

from __future__ import annotations

import json

from typer.testing import CliRunner

from flyer_generator.social.__main__ import app

runner = CliRunner()


def test_list_platforms() -> None:
    result = runner.invoke(app, ["list-platforms"])
    assert result.exit_code == 0
    out = result.stdout
    for p in ("linkedin", "twitter", "instagram", "facebook"):
        assert p in out


def test_list_intents() -> None:
    result = runner.invoke(app, ["list-intents"])
    assert result.exit_code == 0
    assert "announcement" in result.stdout
    assert "value-prop" in result.stdout
    assert "testimonial" in result.stdout


def test_show_rules_linkedin_prints_valid_json() -> None:
    result = runner.invoke(app, ["show-rules", "linkedin"])
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert data["platform"] == "linkedin"
    assert data["body_max_chars"] == 3000


def test_show_rules_unknown_platform_exits_2() -> None:
    result = runner.invoke(app, ["show-rules", "myspace"])
    assert result.exit_code == 2
    # Error can land on stdout or stderr depending on typer version; accept
    # either. CliRunner merges stderr into stdout by default for invoke().
    out = result.stdout + (result.stderr or "" if hasattr(result, "stderr") else "")
    assert "Error" in out or "error" in out.lower()
