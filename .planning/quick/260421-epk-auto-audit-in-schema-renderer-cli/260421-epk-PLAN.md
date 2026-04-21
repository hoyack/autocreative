---
phase: 260421-epk
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - flyer_generator/brochure/schema_renderer/__main__.py
  - tests/brochure/schema_renderer/test_auto_audit.py
autonomous: true
requirements:
  - QUICK-260421-EPK
must_haves:
  truths:
    - "Running the schema_renderer CLI with defaults writes audit.json next to the rendered PNGs"
    - "Users can disable auto-audit via --no-audit for a fast path"
    - "Users can opt into iterative remediation via --iterate-audit N (capped at 3)"
    - "When audit finds warn/error issues the CLI prints a concise per-sheet summary to stderr"
    - "--audit-json PATH routes the sidecar to a caller-supplied location"
    - "The existing --brand-kit integration + base CLI tests still pass"
  artifacts:
    - path: "flyer_generator/brochure/schema_renderer/__main__.py"
      provides: "CLI flags --audit/--no-audit, --iterate-audit, --audit-json and auto-audit step"
    - path: "tests/brochure/schema_renderer/test_auto_audit.py"
      provides: "Auto-audit CLI tests (no network, mocked audit_render/iterate_audit_loop)"
  key_links:
    - from: "flyer_generator/brochure/schema_renderer/__main__.py"
      to: "flyer_generator.brand_kit.audit.audit_render"
      via: "direct call after rasterize, per sheet (outside + inside)"
      pattern: "audit_render\\("
    - from: "flyer_generator/brochure/schema_renderer/__main__.py"
      to: "flyer_generator.brand_kit.audit.iterate_audit_loop"
      via: "invoked only when --iterate-audit > 0 AND issues exist"
      pattern: "iterate_audit_loop\\("
    - from: "audit.json sidecar"
      to: "tests/brochure/schema_renderer/test_auto_audit.py"
      via: "CliRunner + json.loads on audit.json"
      pattern: "audit.json"
---

<objective>
Wire `audit_render` + optional `iterate_audit_loop` into the schema_renderer
CLI so that every render produces an `audit.json` sidecar by default, with
opt-out (`--no-audit`) and opt-in iterative remediation (`--iterate-audit N`).

Purpose: Today every user has to call audit from a Python REPL — unacceptable
UX for a CLI that already owns the full render pipeline. This closes the
Phase 18 loop: generate + render + audit, end-to-end, in one command.

Output:
- Three new typer flags: `--audit/--no-audit`, `--iterate-audit N`, `--audit-json PATH`.
- `audit.json` sidecar in the output directory (or explicit path).
- Per-sheet stderr summary line.
- New test file covering 8+ scenarios; existing tests still green.
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@CLAUDE.md
@.planning/STATE.md
@flyer_generator/brochure/schema_renderer/__main__.py
@flyer_generator/brand_kit/audit.py
@flyer_generator/brand_kit/__init__.py
@flyer_generator/brochure/schema_renderer/text_gen.py
@tests/brand_kit/test_schema_renderer_integration.py

<interfaces>
<!-- Exact signatures — executor uses these directly, no lookup needed. -->

From flyer_generator/brand_kit/audit.py:
```python
def audit_render(
    content: BrochureContent,
    template: TemplateSchema,
    rendered_png_bytes: bytes,
    *,
    side: Literal["outside", "inside"] = "outside",
    cycle: int = 0,
) -> AuditReport: ...

async def iterate_audit_loop(
    content: BrochureContent,
    template: TemplateSchema,
    *,
    render: Callable[[BrochureContent, TemplateSchema], Awaitable[tuple[bytes, bytes]]],
    remediate: RemediateFn | None = None,
    kit: BrandKit | None = None,
    regenerate_fn: Callable[[dict[str, int]], Awaitable[BrochureContent]] | None = None,
    max_cycles: int = 3,
    strict: bool = False,
    side: Literal["outside", "inside"] = "outside",
) -> tuple[AuditReport, BrochureContent, TemplateSchema]: ...

class AuditReport(BaseModel):
    whitespace: dict[str, float]
    contrast: ContrastReport   # has .overall_aa_pass, .pairs, .fails()
    density: dict[str, float]
    issues: list[AuditIssue]   # AuditIssue has .severity ("info"|"warn"|"error"), .category
    cycle: int
    @property
    def is_clean(self) -> bool: ...
```

From flyer_generator/brochure/schema_renderer/text_gen.py:
```python
async def generate_content_from_prompt(
    template: TemplateSchema,
    prompt: str,
    *,
    audience: str | None = None,
    color_accent: str = "#1E3A5F",
    brief: BrochureBrief | None = None,
    contact=None,
    settings: Settings | None = None,
    text_client: TextClient | None = None,
) -> BrochureContent: ...
```
Note: `generate_content_from_prompt` has NO per-key budget override parameter.
See action for scope-down decision on density regen.

From flyer_generator/brochure/schema_renderer/renderer.py (already imported in __main__.py):
```python
def render_schema_brochure(
    tmpl: TemplateSchema,
    content: BrochureContent,
    *,
    images: dict[str, bytes] | None = None,
    textures: dict[str, bytes] | None = None,
    logo_bytes: bytes | None = None,
    accent_override: str | None = None,
) -> tuple[str, str]: ...   # (outside_svg, inside_svg)
```
</interfaces>
</context>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: Wire auto-audit + iterate flags into schema_renderer CLI</name>
  <files>flyer_generator/brochure/schema_renderer/__main__.py</files>
  <read_first>flyer_generator/brochure/schema_renderer/__main__.py</read_first>
  <behavior>
    - With defaults (audit=True, iterate_audit=0), the CLI writes audit.json to &lt;output&gt;/audit.json.
    - audit.json has top-level keys: "outside", "inside", "is_clean_overall".
    - "outside" and "inside" contain the full AuditReport.model_dump() output (keys: whitespace, contrast, density, issues, cycle).
    - With --no-audit, no audit.json is written (fast path).
    - With --audit-json PATH, sidecar goes to PATH instead of &lt;output&gt;/audit.json (parent dir created if needed).
    - When issues include warn/error severity, a one-line summary per sheet is printed to stderr matching:
      "Audit [outside]: AA pass=&lt;bool&gt; (&lt;n_fail&gt;/&lt;n_total&gt; fail), density_min=&lt;float&gt;, whitespace_max=&lt;float&gt;, issues=&lt;N&gt; (&lt;warn&gt; warn, &lt;info&gt; info)"
    - Info-only audits still write audit.json but emit NO stderr summary (quiet-unless-warn+ per spec).
    - With --iterate-audit N (N&gt;0) AND at least one warn/error issue exists, iterate_audit_loop is invoked
      with max_cycles=min(N, 3). Final post-iterate audit (both sides) overwrites audit.json.
    - Without --brand-kit, iterate still runs but contrast remediation is a no-op (kit=None); density
      remediation is ALSO skipped in this plan's scope — see density scope-down below.
    - All existing exit paths, --list-templates, --brand-kit, --prompt, --generate-images unchanged.
  </behavior>
  <action>
Add three typer options to the `render()` function (alongside the existing options):

```python
audit: Annotated[
    bool,
    typer.Option(
        "--audit/--no-audit",
        help="Run audit_render on both sheets after rasterize and write audit.json sidecar.",
    ),
] = True,
iterate_audit: Annotated[
    int,
    typer.Option(
        "--iterate-audit",
        help="Max remediation cycles when audit finds warn/error issues (capped at 3).",
    ),
] = 0,
audit_json: Annotated[
    Optional[Path],
    typer.Option(
        "--audit-json",
        help="Explicit audit.json output path. Defaults to <output>/audit.json.",
    ),
] = None,
```

After the existing rasterize + PDF write block (immediately before the final
"Wrote outputs to" / byte-count echoes — put the audit step BEFORE those echoes
so failures surface cleanly), add the audit step. Structure:

```python
if audit:
    from flyer_generator.brand_kit.audit import audit_render, iterate_audit_loop

    final_template = tmpl  # tmpl already reflects --brand-kit apply if present
    # front_png / back_png are already in scope (from earlier rasterize).

    def _summarize(side: str, report) -> str:
        fails = report.contrast.fails() if hasattr(report.contrast, "fails") else []
        n_fail = len(fails)
        n_total = len(report.contrast.pairs)
        density_min = min(report.density.values()) if report.density else 1.0
        whitespace_max = max(report.whitespace.values()) if report.whitespace else 0.0
        n_warn = sum(1 for i in report.issues if i.severity == "warn")
        n_err = sum(1 for i in report.issues if i.severity == "error")
        n_info = sum(1 for i in report.issues if i.severity == "info")
        return (
            f"Audit [{side}]: AA pass={report.contrast.overall_aa_pass} "
            f"({n_fail}/{n_total} fail), density_min={density_min:.2f}, "
            f"whitespace_max={whitespace_max:.2f}, "
            f"issues={len(report.issues)} ({n_warn + n_err} warn, {n_info} info)"
        )

    report_outside = audit_render(ct, final_template, front_png, side="outside")
    report_inside = audit_render(ct, final_template, back_png, side="inside")

    # Emit stderr summary only when warn/error issues exist (info-only is silent).
    for side_name, rep in (("outside", report_outside), ("inside", report_inside)):
        has_warnplus = any(i.severity in ("warn", "error") for i in rep.issues)
        if has_warnplus or not rep.contrast.overall_aa_pass:
            typer.echo(_summarize(side_name, rep), err=True)

    # Optional iterate loop: only when requested AND issues exist.
    needs_iterate = (
        iterate_audit > 0
        and any(
            i.severity in ("warn", "error")
            for r in (report_outside, report_inside)
            for i in r.issues
        )
    )
    if needs_iterate:
        max_cycles = min(iterate_audit, 3)

        # Render callback for the loop — re-uses the same images/textures/logo in scope.
        async def _render(c, t):
            out_svg, in_svg = render_schema_brochure(
                t, c,
                images=images,
                textures=textures,
                logo_bytes=logo_bytes,
                accent_override=color_accent,
            )
            f = rasterizer.rasterize(out_svg)
            b = rasterizer.rasterize(in_svg)
            return f, b

        # Kit for contrast remediation (only available when --brand-kit was used).
        kit_for_iter = None
        if brand_kit is not None:
            from flyer_generator.brand_kit.storage import load_brand_kit as _lbk
            try:
                kit_for_iter = _lbk(brand_kit)
            except Exception:
                kit_for_iter = None

        # SCOPE DECISION: density regen requires per-key budget override plumbing
        # that generate_content_from_prompt does not yet support. Rather than refactor
        # text_gen, we pass regenerate_fn=None — density issues remain uncorrected by
        # the loop but contrast (when kit available) will be remediated. Documented
        # here so the next caller can plumb budget overrides when needed. This keeps
        # scope tight and is the spec-authorized scope-down.
        final_report_outside, final_content, final_template_iter = asyncio.run(
            iterate_audit_loop(
                ct, final_template,
                render=_render,
                kit=kit_for_iter,
                regenerate_fn=None,
                max_cycles=max_cycles,
                side="outside",
            )
        )
        # Re-render with the (maybe-updated) content/template for the final PNGs
        # so sidecar artifacts reflect the iterated state.
        out_svg2, in_svg2 = render_schema_brochure(
            final_template_iter, final_content,
            images=images, textures=textures,
            logo_bytes=logo_bytes, accent_override=color_accent,
        )
        front_png = rasterizer.rasterize(out_svg2)
        back_png = rasterizer.rasterize(in_svg2)
        (output / "brochure_front.png").write_bytes(front_png)
        (output / "brochure_back.png").write_bytes(back_png)
        if write_svg:
            (output / "outside.svg").write_text(out_svg2, encoding="utf-8")
            (output / "inside.svg").write_text(in_svg2, encoding="utf-8")
        # PDF re-assembly
        pdf = assemble_brochure_pdf(front_png, back_png)
        (output / "brochure_print.pdf").write_bytes(pdf)

        # Re-audit BOTH sides with the iterated content/template.
        report_outside = audit_render(
            final_content, final_template_iter, front_png, side="outside"
        )
        report_inside = audit_render(
            final_content, final_template_iter, back_png, side="inside"
        )
        typer.echo(
            f"Audit iteration complete ({max_cycles} max cycles).", err=True
        )
        for side_name, rep in (("outside", report_outside), ("inside", report_inside)):
            typer.echo(_summarize(side_name, rep), err=True)

    # Write audit.json sidecar.
    combined = {
        "outside": report_outside.model_dump(),
        "inside": report_inside.model_dump(),
        "is_clean_overall": bool(
            report_outside.is_clean and report_inside.is_clean
        ),
    }
    sidecar_path = audit_json if audit_json is not None else (output / "audit.json")
    sidecar_path.parent.mkdir(parents=True, exist_ok=True)
    sidecar_path.write_text(
        json.dumps(combined, indent=2, default=str), encoding="utf-8"
    )
```

Implementation notes:
- `asyncio` is already imported in `__main__.py`; `json` too. No new top-level imports.
- Keep audit imports inside the `if audit:` block so `--no-audit` avoids the
  (cheap, but nonzero) import cost and so tests importing `__main__` do not
  pull the audit module unnecessarily.
- `ct` is the BrochureContent variable name currently used in the file — do
  NOT rename.
- Use `report.contrast.overall_aa_pass` (bool attr on ContrastReport) and
  `report.contrast.pairs` (list) + `report.contrast.fails()` (method).
- `model_dump(default=str)` is needed because ContrastReport may nest enums;
  safer than a plain json.dumps.
- Do NOT remove or alter the existing "Wrote outputs to" echo — leave it as
  the last pair of lines in the function.
  </action>
  <verify>
    <automated>uv run pytest tests/brochure/schema_renderer/test_cli.py tests/brand_kit/test_schema_renderer_integration.py -x -q</automated>
  </verify>
  <done>
    - Three new flags visible in `python -m flyer_generator.brochure.schema_renderer --help`.
    - Default run writes audit.json with keys: outside, inside, is_clean_overall.
    - --no-audit run does not write audit.json.
    - Existing brand-kit integration tests still pass.
    - grep confirms: `audit_render\(`, `iterate_audit_loop\(`, `--no-audit`, `--iterate-audit`, `--audit-json` all present in __main__.py.
  </done>
</task>

<task type="auto" tdd="true">
  <name>Task 2: Add test_auto_audit.py covering flag matrix + iterate path</name>
  <files>tests/brochure/schema_renderer/test_auto_audit.py</files>
  <read_first>tests/brand_kit/test_schema_renderer_integration.py</read_first>
  <behavior>
    Test matrix (all offline — no network, no LLM, no ComfyCloud):
    1. test_audit_default_writes_sidecar: default --audit produces audit.json with outside/inside/is_clean_overall keys; each side has whitespace/contrast/density/issues/cycle.
    2. test_no_audit_skips_sidecar: --no-audit → no audit.json file exists in output.
    3. test_audit_json_custom_path: --audit-json /tmp/foo/bar.json honored; parent dir created.
    4. test_warn_level_prints_stderr_summary: monkeypatch audit_render to return a report with a warn-level issue; stderr contains "Audit [outside]:" and "warn".
    5. test_info_only_is_quiet: monkeypatch audit_render to return a report with ONLY info-level issues + AA pass=True; stderr does NOT contain "Audit [".
    6. test_iterate_audit_zero_is_single_pass: with default --iterate-audit 0, iterate_audit_loop is NOT called even if issues exist.
    7. test_iterate_audit_one_invokes_loop: with --iterate-audit 1 AND warn-level issues, iterate_audit_loop IS called (monkeypatched) with max_cycles=1; audit.json reflects post-iterate report.
    8. test_audit_without_brand_kit: default render without --brand-kit still produces audit.json (iterate call in this case would pass kit=None — test the NO-iterate default path).
  </behavior>
  <action>
Create `tests/brochure/schema_renderer/test_auto_audit.py`. Use the same
fixture/CliRunner pattern as `tests/brand_kit/test_schema_renderer_integration.py`.
Import `app` from `flyer_generator.brochure.schema_renderer.__main__`.

Use typer `CliRunner()` — follow existing patterns. Content JSON fixture mirrors
`_write_content_json` from test_schema_renderer_integration.py.

Monkeypatch `flyer_generator.brochure.schema_renderer.__main__.audit_render`
and `flyer_generator.brochure.schema_renderer.__main__.iterate_audit_loop`
— but note: those imports are INSIDE `if audit:` (see Task 1), so the module
attribute will only exist after the CLI runs. Use the canonical patch target
`flyer_generator.brand_kit.audit.audit_render` / `iterate_audit_loop` — THIS
is where the function is defined; CLI does `from flyer_generator.brand_kit.audit
import audit_render` each run, which resolves to that module's current
binding at call time.

Example skeleton for one test:

```python
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


def _clean_report(side: str = "outside") -> AuditReport:
    return AuditReport(
        whitespace={"front_cover": 0.5},
        contrast=ContrastReport(pairs=[]),
        density={"title": 0.8},
        issues=[],
        cycle=0,
    )


def _warn_report(side: str = "outside") -> AuditReport:
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


def _info_report(side: str = "outside") -> AuditReport:
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


def test_audit_default_writes_sidecar(tmp_path: Path) -> None:
    content_path = _write_content_json(tmp_path / "content.json")
    out_dir = tmp_path / "out"

    result = runner.invoke(app, [
        "--template", "editorial_classic",
        "--content", str(content_path),
        "--output", str(out_dir),
    ])
    assert result.exit_code == 0, (result.stderr or "") + result.stdout
    sidecar = out_dir / "audit.json"
    assert sidecar.exists()
    data = json.loads(sidecar.read_text())
    assert set(data.keys()) >= {"outside", "inside", "is_clean_overall"}
    for side in ("outside", "inside"):
        rep = data[side]
        assert set(rep.keys()) >= {"whitespace", "contrast", "density", "issues", "cycle"}


def test_no_audit_skips_sidecar(tmp_path: Path) -> None:
    content_path = _write_content_json(tmp_path / "content.json")
    out_dir = tmp_path / "out"

    result = runner.invoke(app, [
        "--template", "editorial_classic",
        "--content", str(content_path),
        "--output", str(out_dir),
        "--no-audit",
    ])
    assert result.exit_code == 0, (result.stderr or "") + result.stdout
    assert not (out_dir / "audit.json").exists()


def test_audit_json_custom_path(tmp_path: Path) -> None:
    content_path = _write_content_json(tmp_path / "content.json")
    out_dir = tmp_path / "out"
    custom = tmp_path / "sub" / "nested" / "my-audit.json"

    result = runner.invoke(app, [
        "--template", "editorial_classic",
        "--content", str(content_path),
        "--output", str(out_dir),
        "--audit-json", str(custom),
    ])
    assert result.exit_code == 0, (result.stderr or "") + result.stdout
    assert custom.exists()
    assert not (out_dir / "audit.json").exists()


def test_warn_level_prints_stderr_summary(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(audit_module, "audit_render", lambda *a, **kw: _warn_report())
    content_path = _write_content_json(tmp_path / "content.json")
    out_dir = tmp_path / "out"

    result = runner.invoke(app, [
        "--template", "editorial_classic",
        "--content", str(content_path),
        "--output", str(out_dir),
    ])
    assert result.exit_code == 0, (result.stderr or "") + result.stdout
    stderr = result.stderr or ""
    assert "Audit [outside]:" in stderr
    assert "warn" in stderr


def test_info_only_is_quiet(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(audit_module, "audit_render", lambda *a, **kw: _info_report())
    content_path = _write_content_json(tmp_path / "content.json")
    out_dir = tmp_path / "out"

    result = runner.invoke(app, [
        "--template", "editorial_classic",
        "--content", str(content_path),
        "--output", str(out_dir),
    ])
    assert result.exit_code == 0, (result.stderr or "") + result.stdout
    stderr = result.stderr or ""
    # No warn/error issues and AA passes → no per-sheet summary line.
    assert "Audit [outside]:" not in stderr
    assert "Audit [inside]:" not in stderr
    # But audit.json still exists.
    assert (out_dir / "audit.json").exists()


def test_iterate_audit_zero_is_single_pass(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """With --iterate-audit 0 (default), iterate_audit_loop is NOT called even on warn issues."""
    called = {"n": 0}

    async def _fake_iterate(*a: Any, **kw: Any):
        called["n"] += 1
        raise AssertionError("iterate_audit_loop should not be called with --iterate-audit 0")

    monkeypatch.setattr(audit_module, "audit_render", lambda *a, **kw: _warn_report())
    monkeypatch.setattr(audit_module, "iterate_audit_loop", _fake_iterate)

    content_path = _write_content_json(tmp_path / "content.json")
    out_dir = tmp_path / "out"

    result = runner.invoke(app, [
        "--template", "editorial_classic",
        "--content", str(content_path),
        "--output", str(out_dir),
    ])
    assert result.exit_code == 0, (result.stderr or "") + result.stdout
    assert called["n"] == 0


def test_iterate_audit_one_invokes_loop(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from flyer_generator.brochure.schema_renderer.content_model import BrochureContent

    call_log: dict[str, Any] = {"n": 0, "max_cycles": None}

    # First pass: warn report. After iterate: clean report.
    state = {"phase": "pre-iter"}

    def _fake_audit(*a: Any, **kw: Any):
        if state["phase"] == "pre-iter":
            return _warn_report()
        return _clean_report()

    async def _fake_iterate(content, template, *, render, max_cycles, kit=None,
                             regenerate_fn=None, remediate=None,
                             strict=False, side="outside"):
        call_log["n"] += 1
        call_log["max_cycles"] = max_cycles
        state["phase"] = "post-iter"
        # Return (report, content, template) — content/template unchanged.
        return _clean_report(), content, template

    monkeypatch.setattr(audit_module, "audit_render", _fake_audit)
    monkeypatch.setattr(audit_module, "iterate_audit_loop", _fake_iterate)

    content_path = _write_content_json(tmp_path / "content.json")
    out_dir = tmp_path / "out"

    result = runner.invoke(app, [
        "--template", "editorial_classic",
        "--content", str(content_path),
        "--output", str(out_dir),
        "--iterate-audit", "1",
    ])
    assert result.exit_code == 0, (result.stderr or "") + result.stdout
    assert call_log["n"] == 1
    assert call_log["max_cycles"] == 1
    # Final audit.json reflects the post-iterate clean state.
    data = json.loads((out_dir / "audit.json").read_text())
    assert data["is_clean_overall"] is True


def test_iterate_audit_caps_at_three(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """--iterate-audit 99 must be clamped to max_cycles=3."""
    call_log: dict[str, Any] = {"max_cycles": None}

    async def _fake_iterate(content, template, *, render, max_cycles, kit=None,
                             regenerate_fn=None, remediate=None,
                             strict=False, side="outside"):
        call_log["max_cycles"] = max_cycles
        return _clean_report(), content, template

    state = {"phase": "pre"}

    def _fake_audit(*a: Any, **kw: Any):
        return _warn_report() if state["phase"] == "pre" else _clean_report()

    def _flip_after(*a: Any, **kw: Any):
        state["phase"] = "post"
        return _warn_report()

    monkeypatch.setattr(audit_module, "audit_render", _fake_audit)
    monkeypatch.setattr(audit_module, "iterate_audit_loop", _fake_iterate)

    content_path = _write_content_json(tmp_path / "content.json")
    out_dir = tmp_path / "out"

    result = runner.invoke(app, [
        "--template", "editorial_classic",
        "--content", str(content_path),
        "--output", str(out_dir),
        "--iterate-audit", "99",
    ])
    assert result.exit_code == 0, (result.stderr or "") + result.stdout
    assert call_log["max_cycles"] == 3


def test_audit_without_brand_kit(tmp_path: Path) -> None:
    """Plain render (no --brand-kit) still produces audit.json."""
    content_path = _write_content_json(tmp_path / "content.json")
    out_dir = tmp_path / "out"

    result = runner.invoke(app, [
        "--template", "editorial_classic",
        "--content", str(content_path),
        "--output", str(out_dir),
    ])
    assert result.exit_code == 0, (result.stderr or "") + result.stdout
    assert (out_dir / "audit.json").exists()
```

Notes:
- `runner.invoke(app, [...])` with typer's CliRunner. Check existing
  `tests/brand_kit/test_schema_renderer_integration.py` for boilerplate
  (`CliRunner()` already works with typer commands in this repo).
- Do not mock `rasterizer` or `render_schema_brochure` — the "happy path"
  tests need real renders so audit.json shape is exercised end-to-end.
  Only the audit functions are monkeypatched.
- For `test_iterate_audit_one_invokes_loop`, the CLI Task 1 action wraps
  `iterate_audit_loop` in `asyncio.run(...)`. The monkeypatched fake must
  be an async def so `asyncio.run` gets a coroutine.
  </action>
  <verify>
    <automated>uv run pytest tests/brochure/schema_renderer/test_auto_audit.py -x -v</automated>
  </verify>
  <done>
    - tests/brochure/schema_renderer/test_auto_audit.py exists with at least 8 test functions.
    - All 8+ tests pass.
    - Full suite: `uv run pytest -q` passes with total count ≥ 920 tests (8+ new).
    - Existing tests in `tests/brochure/schema_renderer/test_cli.py` (if any)
      and `tests/brand_kit/test_schema_renderer_integration.py` still green.
  </done>
</task>

</tasks>

<verification>
Run the focused audit tests, then a full suite:

```bash
uv run pytest tests/brochure/schema_renderer/test_auto_audit.py tests/brand_kit/test_schema_renderer_integration.py -x -v
uv run pytest -q
```

Grep checks:
```bash
grep -n "audit_render\|iterate_audit_loop\|--no-audit\|--iterate-audit\|--audit-json" \
  flyer_generator/brochure/schema_renderer/__main__.py
```
</verification>

<success_criteria>
- `--audit/--no-audit`, `--iterate-audit`, `--audit-json` flags in the CLI.
- Default run writes `<output>/audit.json` with {outside, inside, is_clean_overall}.
- `--no-audit` skips the sidecar (fast path).
- Warn/error issues produce a one-line per-sheet stderr summary; info-only is silent.
- `--iterate-audit N` invokes `iterate_audit_loop` with max_cycles=min(N, 3) when
  warn/error issues exist, and re-audits + re-writes sidecar.
- 8+ new tests pass offline; full suite green at ≥920 tests.
- No changes to audit_render / iterate_audit_loop / generate_content_from_prompt
  public signatures.
</success_criteria>

<output>
After completion, the executor writes
`.planning/quick/260421-epk-auto-audit-in-schema-renderer-cli/260421-epk-01-SUMMARY.md`
per the standard SUMMARY template.
</output>
