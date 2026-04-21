"""Tests for the schema_renderer CLI auto-audit flow (--audit / --iterate-audit / --audit-json).

All tests run offline: no ComfyCloud calls, no LLM calls. Real rasterization
happens for happy-path audit.json shape checks; audit_render and
iterate_audit_loop are monkeypatched where we need deterministic issue shapes.

Patch target: `flyer_generator.brand_kit.audit.audit_render` (and
`iterate_audit_loop`) — the CLI does `from flyer_generator.brand_kit import
audit as _audit_mod` and calls `_audit_mod.audit_render(...)` so attribute
lookup happens at call time against the patched module.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from typer.testing import CliRunner

from flyer_generator.brand_kit import audit as audit_module
from flyer_generator.brand_kit.audit import AuditIssue, AuditReport
from flyer_generator.brand_kit.contrast import ContrastReport
from flyer_generator.brochure.schema_renderer.__main__ import app

runner = CliRunner()


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


def _clean_report() -> AuditReport:
    return AuditReport(
        whitespace={"front_cover": 0.5},
        contrast=ContrastReport(pairs=[]),
        density={"title": 0.8},
        issues=[],
        cycle=0,
    )


def _warn_report() -> AuditReport:
    return AuditReport(
        whitespace={"front_cover": 0.95},
        contrast=ContrastReport(pairs=[]),
        density={"title": 0.3},
        issues=[
            AuditIssue(
                severity="warn",
                category="whitespace",
                panel="front_cover",
                detail="too empty",
            )
        ],
        cycle=0,
    )


def _info_report() -> AuditReport:
    return AuditReport(
        whitespace={"front_cover": 0.5},
        contrast=ContrastReport(pairs=[]),
        density={"title": 0.3},
        issues=[
            AuditIssue(
                severity="info",
                category="density",
                panel="front_cover",
                content_key="title",
                detail="under-filled",
            )
        ],
        cycle=0,
    )


# --------------------------------------------------------------------------- #
# Happy path: real audit_render, real rasterize, real shape checks
# --------------------------------------------------------------------------- #


def test_audit_default_writes_sidecar(tmp_path: Path) -> None:
    content_path = _write_content_json(tmp_path / "content.json")
    out_dir = tmp_path / "out"

    result = runner.invoke(
        app,
        [
            "--template", "editorial_classic",
            "--content", str(content_path),
            "--output", str(out_dir),
        ],
    )
    assert result.exit_code == 0, (result.stderr or "") + result.stdout
    sidecar = out_dir / "audit.json"
    assert sidecar.exists()
    data = json.loads(sidecar.read_text())
    assert set(data.keys()) >= {"outside", "inside", "is_clean_overall"}
    for side in ("outside", "inside"):
        rep = data[side]
        assert set(rep.keys()) >= {"whitespace", "contrast", "density", "issues", "cycle"}
    assert isinstance(data["is_clean_overall"], bool)


def test_no_audit_skips_sidecar(tmp_path: Path) -> None:
    content_path = _write_content_json(tmp_path / "content.json")
    out_dir = tmp_path / "out"

    result = runner.invoke(
        app,
        [
            "--template", "editorial_classic",
            "--content", str(content_path),
            "--output", str(out_dir),
            "--no-audit",
        ],
    )
    assert result.exit_code == 0, (result.stderr or "") + result.stdout
    assert not (out_dir / "audit.json").exists()
    # But core render artifacts still land.
    assert (out_dir / "brochure_front.png").exists()
    assert (out_dir / "brochure_back.png").exists()


def test_audit_json_custom_path(tmp_path: Path) -> None:
    content_path = _write_content_json(tmp_path / "content.json")
    out_dir = tmp_path / "out"
    custom = tmp_path / "sub" / "nested" / "my-audit.json"

    result = runner.invoke(
        app,
        [
            "--template", "editorial_classic",
            "--content", str(content_path),
            "--output", str(out_dir),
            "--audit-json", str(custom),
        ],
    )
    assert result.exit_code == 0, (result.stderr or "") + result.stdout
    assert custom.exists()
    # Sidecar went to the custom path — not the default inside the output dir.
    assert not (out_dir / "audit.json").exists()


def test_audit_without_brand_kit(tmp_path: Path) -> None:
    """Plain render without --brand-kit still produces audit.json (no kit, no iterate)."""
    content_path = _write_content_json(tmp_path / "content.json")
    out_dir = tmp_path / "out"

    result = runner.invoke(
        app,
        [
            "--template", "editorial_classic",
            "--content", str(content_path),
            "--output", str(out_dir),
        ],
    )
    assert result.exit_code == 0, (result.stderr or "") + result.stdout
    assert (out_dir / "audit.json").exists()


# --------------------------------------------------------------------------- #
# Stderr summary behavior — monkeypatch audit_render for deterministic issue sets
# --------------------------------------------------------------------------- #


def test_warn_level_prints_stderr_summary(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        audit_module, "audit_render", lambda *a, **kw: _warn_report()
    )
    content_path = _write_content_json(tmp_path / "content.json")
    out_dir = tmp_path / "out"

    result = runner.invoke(
        app,
        [
            "--template", "editorial_classic",
            "--content", str(content_path),
            "--output", str(out_dir),
        ],
    )
    assert result.exit_code == 0, (result.stderr or "") + result.stdout
    stderr = result.stderr or ""
    assert "Audit [outside]:" in stderr
    assert "warn" in stderr
    # Sidecar still written.
    assert (out_dir / "audit.json").exists()


def test_info_only_is_quiet(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        audit_module, "audit_render", lambda *a, **kw: _info_report()
    )
    content_path = _write_content_json(tmp_path / "content.json")
    out_dir = tmp_path / "out"

    result = runner.invoke(
        app,
        [
            "--template", "editorial_classic",
            "--content", str(content_path),
            "--output", str(out_dir),
        ],
    )
    assert result.exit_code == 0, (result.stderr or "") + result.stdout
    stderr = result.stderr or ""
    # No warn/error issues AND AA passes → no per-sheet summary line.
    assert "Audit [outside]:" not in stderr
    assert "Audit [inside]:" not in stderr
    # Sidecar is still written.
    assert (out_dir / "audit.json").exists()


# --------------------------------------------------------------------------- #
# Iterate loop behavior
# --------------------------------------------------------------------------- #


def test_iterate_audit_zero_is_single_pass(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Default --iterate-audit 0 MUST NOT invoke iterate_audit_loop even on warns."""

    async def _fake_iterate(*a: Any, **kw: Any):  # pragma: no cover - assertion below
        raise AssertionError(
            "iterate_audit_loop should not be called with --iterate-audit 0"
        )

    monkeypatch.setattr(
        audit_module, "audit_render", lambda *a, **kw: _warn_report()
    )
    monkeypatch.setattr(audit_module, "iterate_audit_loop", _fake_iterate)

    content_path = _write_content_json(tmp_path / "content.json")
    out_dir = tmp_path / "out"

    result = runner.invoke(
        app,
        [
            "--template", "editorial_classic",
            "--content", str(content_path),
            "--output", str(out_dir),
        ],
    )
    assert result.exit_code == 0, (result.stderr or "") + result.stdout


def test_iterate_audit_one_invokes_loop(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    call_log: dict[str, Any] = {"n": 0, "max_cycles": None}
    # State machine: first two audit_render calls (outside, inside) return warn;
    # after iterate runs, subsequent calls return clean.
    state = {"phase": "pre-iter"}

    def _fake_audit(*a: Any, **kw: Any) -> AuditReport:
        if state["phase"] == "pre-iter":
            return _warn_report()
        return _clean_report()

    async def _fake_iterate(
        content, template, *, render, max_cycles,
        kit=None, regenerate_fn=None, remediate=None,
        strict=False, side="outside",
    ):
        call_log["n"] += 1
        call_log["max_cycles"] = max_cycles
        state["phase"] = "post-iter"
        return _clean_report(), content, template

    monkeypatch.setattr(audit_module, "audit_render", _fake_audit)
    monkeypatch.setattr(audit_module, "iterate_audit_loop", _fake_iterate)

    content_path = _write_content_json(tmp_path / "content.json")
    out_dir = tmp_path / "out"

    result = runner.invoke(
        app,
        [
            "--template", "editorial_classic",
            "--content", str(content_path),
            "--output", str(out_dir),
            "--iterate-audit", "1",
        ],
    )
    assert result.exit_code == 0, (result.stderr or "") + result.stdout
    assert call_log["n"] == 1
    assert call_log["max_cycles"] == 1
    data = json.loads((out_dir / "audit.json").read_text())
    # Post-iterate audit reports clean.
    assert data["is_clean_overall"] is True


def test_iterate_audit_caps_at_three(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """--iterate-audit 99 MUST be clamped to max_cycles=3."""
    call_log: dict[str, Any] = {"max_cycles": None}
    state = {"phase": "pre-iter"}

    def _fake_audit(*a: Any, **kw: Any) -> AuditReport:
        if state["phase"] == "pre-iter":
            return _warn_report()
        return _clean_report()

    async def _fake_iterate(
        content, template, *, render, max_cycles,
        kit=None, regenerate_fn=None, remediate=None,
        strict=False, side="outside",
    ):
        call_log["max_cycles"] = max_cycles
        state["phase"] = "post-iter"
        return _clean_report(), content, template

    monkeypatch.setattr(audit_module, "audit_render", _fake_audit)
    monkeypatch.setattr(audit_module, "iterate_audit_loop", _fake_iterate)

    content_path = _write_content_json(tmp_path / "content.json")
    out_dir = tmp_path / "out"

    result = runner.invoke(
        app,
        [
            "--template", "editorial_classic",
            "--content", str(content_path),
            "--output", str(out_dir),
            "--iterate-audit", "99",
        ],
    )
    assert result.exit_code == 0, (result.stderr or "") + result.stdout
    assert call_log["max_cycles"] == 3
