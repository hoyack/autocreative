# Phase 5: Brochure Models & Panel Geometry - Context

**Gathered:** 2026-04-18
**Status:** Ready for planning
**Mode:** `--auto` (Claude selected recommended defaults per brochure-plan.md)

<domain>
## Phase Boundary

Phase 5 delivers the **data layer + pure-function panel geometry** for the brochure generator — nothing else. Specifically:

- New Pydantic v2 models under `flyer_generator/brochure/models.py`: `BrochureInput`, `BrochureSection`, `BrochureBackPanel`, `ContactBlock`, `BrochureOutput`, `ResolvedBrochureLayout`, `PanelRect`.
- New pure geometry module `flyer_generator/brochure/stages/layout.py`: given sheet dimensions, bleed, and safe-zone insets, returns pixel rectangles for all six tri-fold panels on an outside sheet + inside sheet, plus fold-line x-coordinates and crop-mark corner points.
- Unit tests in `tests/brochure/` covering both model validation and geometry math.

Out of scope for Phase 5 (later phases):
- Any ComfyCloud, Anthropic, or Ollama calls (Phase 6)
- SVG composition or rasterization (Phase 7)
- PDF assembly / reportlab (Phase 8)
- CLI surface / public API (Phase 9)
- Backward-compat shims for legacy flyer models

</domain>

<decisions>
## Implementation Decisions

### Module Layout
- **D-05-01:** New parallel module `flyer_generator/brochure/` alongside existing flyer code. Not a rename/refactor of the current structure. Flyer pipeline stays untouched.
- **D-05-02:** Phase 5 creates `flyer_generator/brochure/__init__.py`, `flyer_generator/brochure/models.py`, `flyer_generator/brochure/stages/__init__.py`, `flyer_generator/brochure/stages/layout.py`. Nothing else in this phase.
- **D-05-03:** `flyer_generator/brochure/__init__.py` exports the models from this phase only. Pipeline/generator exports are added by later phases.

### Data Model Shape
Following `docs/brochure-plan.md` §3 verbatim.
- **D-05-04:** `BrochureInput` fields: `title: str`, `subtitle: str | None`, `hero_concept: str`, `style_preset: str`, `color_accent: HexColor`, `org: str`, `contact: ContactBlock | None`, `sections: list[BrochureSection]` (min 2, max 5), `back_panel: BrochureBackPanel | None`.
- **D-05-05:** `BrochureSection` fields: `heading: str`, `body: str`, `icon_hint: str | None`. `icon_hint` is captured but unused in v1 (no behaviour attached).
- **D-05-06:** `BrochureBackPanel` fields: `kind: Literal["cta", "bio", "map_stub", "contact"]`, `content: str`. Templates resolved at compose time, not in this phase.
- **D-05-07:** `ContactBlock` fields (all `str | None` so callers can fill partials): `name`, `phone`, `email`, `url`, `address`.
- **D-05-08:** `BrochureOutput` fields: `front_png_bytes: bytes`, `back_png_bytes: bytes`, `pdf_bytes: bytes`, `dimensions: tuple[int, int]`, `attempts_used: int`, `hero_vision_verdict: VisionVerdict` (reuse flyer model), `trace_id: str`. `.save(dir: Path)` method writes three files: `brochure_front.png`, `brochure_back.png`, `brochure_print.pdf`. Phase 5 leaves `png_bytes`/`pdf_bytes` as typed-bytes placeholders (empty allowed) so the model is importable before Phases 7/8 populate them.
- **D-05-09:** Hex color validation reuses the regex+validator pattern from `flyer_generator/models.py` (`_HEX_COLOR_RE`). Export the validator as a module-level helper `validate_hex_color` in `flyer_generator/brochure/models.py` so `color_accent` on `BrochureInput` reuses it (rather than duplicating or depending back into the flyer module's private regex).
- **D-05-10:** Section count enforced via Pydantic `Field(min_length=2, max_length=5)`. If a 5th section overflows to a compact list at compose time, that is a Phase 7 concern — Phase 5 just guards the bound.
- **D-05-11:** `model_config = ConfigDict(extra="forbid")` on every new Pydantic model. Matches strictness and surfaces typos early.

### Panel Geometry
Following `docs/brochure-plan.md` §2 verbatim.
- **D-05-12:** All measurements derived from three named constants in `flyer_generator/brochure/stages/layout.py`:
  - `LETTER_LANDSCAPE_INCHES = (11.0, 8.5)` (width, height)
  - `BLEED_INCHES = 0.125`
  - `SAFE_INCHES = 0.25`
  - `DPI = 300`
  Derived: trim px `(3300, 2550)`, bleed canvas px `(3375, 2625)`.
- **D-05-13:** Panels are equal width in v1 (`sheet_width_px // 3` each). Tuck-flap asymmetry is deferred — callout in code + test comment only.
- **D-05-14:** Outside sheet panel order (left→right when viewing the printed outside): `back_cover (panel 6)`, `front_cover (panel 1)`, `tuck_flap (panel 2)`. Inside sheet (left→right on printed inside): `inner_left (panel 3)`, `inner_center (panel 4)`, `inner_right (panel 5)`.
- **D-05-15:** `PanelRect` is a Pydantic model with fields `name`, `index` (1-6), `sheet` (`Literal["outside", "inside"]`), `bleed_rect` (x, y, w, h in px on the bleed canvas), `trim_rect` (x, y, w, h), `safe_rect` (x, y, w, h). All coordinates are origin-top-left in pixels.
- **D-05-16:** `ResolvedBrochureLayout` has fields: `outside_panels: list[PanelRect]` (length 3), `inside_panels: list[PanelRect]` (length 3), `fold_lines_outside: list[int]` (2 x-coords), `fold_lines_inside: list[int]` (2 x-coords), `crop_marks: list[tuple[int, int]]` (16 points — 4 corners × 2 sheets × 2 tick segments, or simplified to 8 corner origins; see test for exact count).
- **D-05-17:** Top-level function is `compute_panel_layout() -> ResolvedBrochureLayout`. Pure, no args required (all measurements are constants). If a caller ever wants to override DPI / sheet size (A4, 11×17), we add optional params then — YAGNI for Phase 5.
- **D-05-18:** No I/O, no logging, no dependencies outside Pydantic inside the geometry module. Layout math uses plain `int`/`float`; pixel coords are always `int` (round using banker's rounding by casting `int(round(x))` only at the final assignment).

### Testing
- **D-05-19:** Test files in `tests/brochure/` (new directory) — parallel to `tests/`.
  - `tests/brochure/__init__.py` (empty)
  - `tests/brochure/test_models.py` — Pydantic validation: valid `BrochureInput` round-trips; hex validation rejects `"red"`, `"#ABC"`, `"#GGGGGG"`; section count boundary (1 rejected, 2 ok, 5 ok, 6 rejected); `BrochureBackPanel.kind` literal enforcement; `ContactBlock` all-None default; `BrochureOutput.save()` writes three files.
  - `tests/brochure/test_layout.py` — `compute_panel_layout()` returns 3+3 panels with `bleed_rect` total summing to the full sheet bleed canvas; `trim_rect` total summing to the trim canvas (no overlap, no gap); safe_rect is properly inset on all sides; fold lines at 1/3 and 2/3 of trim width; crop marks in the bleed area only (none inside trim).
- **D-05-20:** No ComfyCloud mocks, no anthropic mocks, no httpx in this phase — pure offline unit tests.
- **D-05-21:** Add a fixture file `tests/brochure/fixtures/sample_brochures.py` with 2 canned `BrochureInput` values (one minimal: 2 sections, no contact / back_panel; one full: 5 sections + contact + back_panel). Reused by later phases.

### Claude's Discretion
- Exact file-layout under `flyer_generator/brochure/stages/` (adding more modules later is fine).
- Ordering of fields inside each model (conventional: required first, optional last).
- Exception type names for validation errors (use Pydantic's `ValidationError` — no custom types this phase).
- Crop-mark point count / representation, as long as the test asserts: (a) exactly 8 corners (2 sheets × 4 corners), (b) each corner is in the bleed margin not inside trim. `list[tuple[int, int]]` of 8 origin points is fine.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Brochure Design (authoritative for this phase)
- `docs/brochure-plan.md` §2 — Print Format & Geometry (dimensions, bleed, safe zone, fold layout, crop marks)
- `docs/brochure-plan.md` §3 — Data Model (all field tables for BrochureInput, BrochureSection, BrochureBackPanel, ContactBlock, BrochureOutput)
- `docs/brochure-plan.md` §4 — Pipeline & Module Layout (confirms `flyer_generator/brochure/` tree)
- `docs/brochure-plan.md` §10 — Testing Strategy (confirms `tests/brochure/` parallel tree and fixtures)
- `docs/brochure-plan.md` §12 — Shared vs. New Code (confirms `VisionVerdict` is reused for `BrochureOutput.hero_vision_verdict`)

### Flyer Patterns to Mirror
- `flyer_generator/models.py` — Pydantic v2 style: `BaseModel`, `ConfigDict`, `Field`, `field_validator`, `model_validator`, hex color regex/validator, `.save()` method pattern on `FlyerOutput`
- `flyer_generator/zones.py` (not read this phase, referenced for pattern only) — how `ZoneCoord`/`ZoneName` types are structured if we later want `PanelName` as a `Literal[...]`

### Project Conventions
- `CLAUDE.md` — Python 3.11+, Pydantic v2, pytest + pytest-asyncio (async not needed this phase), ruff + pyright
- `.planning/PROJECT.md` — project vision (not re-read; no conflict detected)

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `flyer_generator.models.VisionVerdict` — imported into `BrochureOutput` as-is (no new type needed).
- Hex color regex `_HEX_COLOR_RE = re.compile(r"^#[0-9A-Fa-f]{6}$")` in `flyer_generator/models.py` — same pattern, re-implement locally in `flyer_generator/brochure/models.py` (don't import a private) and export as `validate_hex_color`.
- `FlyerOutput.save(path: Path)` — pattern for `BrochureOutput.save(dir: Path)`. Brochure version takes a **directory** (writes 3 files) rather than a single PNG path.
- `ConfigDict(arbitrary_types_allowed=True)` usage on `ResolvedLayout` — not needed for `ResolvedBrochureLayout` because all contents are plain Pydantic models / primitives.

### Established Patterns
- Public modules stay thin — business logic lives in `stages/`. Phase 5 respects this (`models.py` is pure data; `stages/layout.py` is pure math).
- Tests live in `tests/` mirroring module structure. Brochure gets its own subtree.
- No backward-compat shims. New module — additive only.
- Hex color validation via `field_validator("color_accent")` returning the (normalised) string. Raises `ValueError` on mismatch, which Pydantic wraps as `ValidationError`.

### Integration Points
- Phase 5 produces no callers. Phase 6 will import `BrochureInput` + `compute_panel_layout()`; Phase 7 composer will consume `ResolvedBrochureLayout`; Phase 8 PDF will consume `BrochureOutput`; Phase 9 CLI will build `BrochureInput` from flags or JSON. No wiring needed this phase.
- `flyer_generator/__init__.py` is NOT touched in Phase 5. Top-level brochure exports are added in Phase 9 to avoid exposing incomplete surface area.

</code_context>

<specifics>
## Specific Ideas

- Panel rectangles must not overlap and must sum to the full sheet canvas — this is a hard test invariant.
- Safe zones must be **fully inside** their owning panel's trim rect (inset by 0.25″ = 75 px on all four sides).
- Fold lines are **inside trim area**, not in bleed — they mark where the paper folds, not where it's trimmed.
- Crop marks are drawn **in bleed** only (outside the trim rect), at trim corners.
- The tuck-flap panel's position on the outside sheet is visually to the **right** of the front cover when looking at the printed face. When the sheet is folded, the tuck-flap folds behind to seat against the back cover panel.

## Open Micro-Choices (Planning phase decides)

- Whether `PanelRect` field `index` is `int` in 1-6 or `Literal[1,2,3,4,5,6]`. Either is fine; `Literal` catches typos at mypy time but `int` is simpler.
- Whether to expose a small enum `class PanelName(StrEnum)` or just use `Literal["back_cover","front_cover","tuck_flap","inner_left","inner_center","inner_right"]` as the `name` field type. Lean toward `Literal` — no runtime instantiations needed.

</specifics>

<deferred>
## Deferred Ideas

- Tuck-flap 1/16″ narrowing (visual/print refinement) — Phase 7 cosmetic follow-up after real fold test.
- A4 landscape + 11×17 half-fold variants — backlog / later phase (docs/brochure-plan.md §13 open question #3).
- Icon rendering for `BrochureSection.icon_hint` — backlog (docs/brochure-plan.md §13 open question #2).
- `BrochurePDFError` exception — introduced in Phase 8, not 5.
- Custom exception hierarchy for brochure-specific validation failures — Pydantic `ValidationError` is sufficient for now.

</deferred>

---

*Phase: 05-brochure-models-panel-geometry*
*Context gathered: 2026-04-18*