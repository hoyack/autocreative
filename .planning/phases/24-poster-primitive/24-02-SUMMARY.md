---
phase: 24-poster-primitive
plan: 02
subsystem: pipeline
tags: [flyer-generator, poster, canvas-dimensions, refactor, tdd, back-compat]

# Dependency graph
requires:
  - phase: 22-flyer-templates
    provides: PosterComposer (template-driven, hardcoded 1080-canvas)
  - phase: 03-composition
    provides: ImagePreprocessor / Rasterizer (already-parameterized stages)
provides:
  - FlyerGenerator(canvas_dimensions=(W, H)) injects canvas through entire stage chain
  - ImagePreprocessor(final_dimensions=(W, H)) — parameterized upscale target
  - PosterComposer(canvas_width=W) — instance-level canvas / margin (was module-level)
  - FlyerOutput.dimensions reflects actual canvas, not hardcoded literal
affects: [24-03 templates, 24-04 worker, 24-05 routes, 24-06 frontend]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - keyword-only-canvas_dimensions-kwarg-on-FlyerGenerator-with-None-fallback
    - design-grid-coords-in-svg-with-scaled-outer-width-height
    - module-level-helpers-keep-back-compat-via-kwarg-defaults

key-files:
  created:
    - tests/unit/test_preprocessor_canvas_dimensions.py
    - tests/unit/test_composer_canvas_dimensions.py
    - tests/test_pipeline_canvas_dimensions.py
  modified:
    - flyer_generator/pipeline.py
    - flyer_generator/stages/preprocessor.py
    - flyer_generator/stages/composer.py

key-decisions:
  - "Keep SVG viewBox at design-grid 0 0 1080 1920 always; only outer SVG width/height scale with canvas_width. This preserves byte-identical output at canvas_width=1080 and lets cairosvg's output_width/output_height (set by Rasterizer) be the source of truth for the final raster size."
  - "Module-level _CANVAS_WIDTH/_MARGIN_PX renamed to _DESIGN_CANVAS_WIDTH/_DESIGN_MARGIN_PX to communicate they are the design coord system, not the runtime canvas. Runtime canvas/margin live on PosterComposer instance (self._canvas_width / self._margin_px)."
  - "Module-level _title_params() function gains optional canvas_width / margin_px kwargs (defaults preserve pre-refactor behavior). Tests/test_composer.py imports _title_params and _wrap_text directly so these helpers must remain module-scoped."
  - "ImagePreprocessor keeps the class-level FINAL_DIMENSIONS = (1080, 1920) for introspection / back-compat; the runtime upscale target lives on the instance (self._final_dimensions)."
  - "canvas_dimensions kwarg is keyword-only and defaults to None (which resolves to (1080, 1920) inside __init__). Keyword-only enforcement prevents accidental positional misuse and signals the kwarg is optional."

patterns-established:
  - "Pipeline-orchestrator parameter threading: FlyerGenerator receives canvas dimensions once and threads them to every stage that cares (preprocessor, composer, rasterizer, FlyerOutput) — no fork of the renderer needed."
  - "Design-grid + outer-scale composer: SVG interior keeps a fixed coordinate system; outer width/height attributes scale with the runtime canvas. Aligns with how cairosvg rasterizes (output dims override SVG dims)."

requirements-completed: [PO-02]

# Metrics
duration: 25min
completed: 2026-04-25
---

# Phase 24 Plan 02: FlyerGenerator canvas_dimensions kwarg Summary

**Parameterized the entire flyer pipeline (preprocessor / composer / rasterizer / FlyerOutput) on a per-call canvas size while keeping the existing 1080×1920 flyer worker call site byte-identical — pipeline reuse, not fork.**

## Performance

- **Duration:** ~25 min (4 commits including TDD RED/GREEN gates)
- **Started:** 2026-04-25T07:22Z
- **Completed:** 2026-04-25T07:47Z
- **Tasks:** 2 / 2 complete
- **Files modified:** 3 source + 3 new test files = 6 total

## Accomplishments

- **PO-02 closed.** `FlyerGenerator(canvas_dimensions=(W, H))` now wires every stage to that canvas in one place. Plan 24-04 worker can call `FlyerGenerator(canvas_dimensions=size_to_dim(size))` directly.
- **Zero regression.** Full pytest sweep (`tests/ -q -k "not slow" --ignore=tests/integration`): **1619 passed, 0 failed.** Phase 23 baseline 1456 → +163 (Phase 23-06 perms + 25 from this plan).
- **Module-level mutable globals retired.** `_CANVAS_WIDTH` and `_MARGIN_PX` moved from module scope to `PosterComposer` instance state, removing a hidden state hazard for any future multi-canvas test runs.
- **Back-compat asserted explicitly.** Two new pipeline tests pin the no-kwarg path to `(1080, 1920)` and check that `_preprocessor._final_dimensions`, `_composer._canvas_width`, `_rasterizer._width / _height` all default correctly.

## Task Commits

Each task was committed atomically (TDD RED + GREEN per task):

1. **Task 1: Parameterize ImagePreprocessor + PosterComposer**
   - RED:  `3e26ffa` — `test(24-02): add failing tests for ImagePreprocessor + PosterComposer canvas-dim parameterization`
   - GREEN:`15c8eb1` — `feat(24-02): parameterize ImagePreprocessor.final_dimensions + PosterComposer.canvas_width`

2. **Task 2: FlyerGenerator + FlyerOutput accept canvas_dimensions**
   - RED:  `6e2bc3f` — `test(24-02): add failing tests for FlyerGenerator canvas_dimensions kwarg`
   - GREEN:`645481a` — `feat(24-02): FlyerGenerator accepts canvas_dimensions kwarg (PO-02)`

## Files Created/Modified

### Created

- `tests/unit/test_preprocessor_canvas_dimensions.py` — 5 tests: default constructor + 3 poster sizes (5400×7200, 7200×10800, 8100×12000) round-trip through `upscale()` and emit correctly-sized PNGs.
- `tests/unit/test_composer_canvas_dimensions.py` — 10 tests: default `canvas_width=1080` and proportional `_margin_px` scaling at 5400/7200/8100; SVG `width="..."` matches constructor; module-level `_CANVAS_WIDTH` / `_MARGIN_PX` removed; constructor signature accepts `canvas_width=1080`.
- `tests/test_pipeline_canvas_dimensions.py` — 10 tests: keyword-only `canvas_dimensions` kwarg with default `None`; back-compat `(1080, 1920)`; parametrized poster sizes thread to preprocessor / composer / rasterizer; end-to-end `FlyerOutput.dimensions` reflects the kwarg.

### Modified

- `flyer_generator/pipeline.py` — `FlyerGenerator.__init__` gains `canvas_dimensions: tuple[int, int] | None = None` keyword-only; falls back to `(1080, 1920)`. Threads dims to `ImagePreprocessor(final_dimensions=...)`, `PosterComposer(canvas_width=...)`, `Rasterizer(width=W, height=H)`. `FlyerOutput.dimensions=self._canvas_dimensions` (was hardcoded `(1080, 1920)`).
- `flyer_generator/stages/preprocessor.py` — `ImagePreprocessor.__init__(final_dimensions=(1080, 1920))`; `upscale()` uses `self._final_dimensions`; class-level `FINAL_DIMENSIONS` kept for introspection.
- `flyer_generator/stages/composer.py` — `PosterComposer.__init__(canvas_width=1080)`; computes `self._canvas_width`, `self._margin_px = round(canvas_width × 60 / 1080)`, `self._canvas_height = round(canvas_width × 1920 / 1080)`, `self._scale`. Outer `<svg width="{canvas_width}" height="{canvas_height}" viewBox="0 0 1080 1920">`. Module-level `_CANVAS_WIDTH` / `_MARGIN_PX` renamed to `_DESIGN_CANVAS_WIDTH` / `_DESIGN_CANVAS_HEIGHT` / `_DESIGN_MARGIN_PX`. Module-level `_title_params(...)` gains `canvas_width` / `margin_px` kwargs (defaults preserve pre-refactor behavior — `tests/test_composer.py` imports it directly).

## Diffs (key sections)

### `pipeline.py::FlyerGenerator.__init__`

```python
def __init__(
    self,
    settings: Settings,
    presets: PresetRegistry | None = None,
    http_client: httpx.AsyncClient | None = None,
    *,
    canvas_dimensions: tuple[int, int] | None = None,  # NEW kwarg
) -> None:
    self.settings = settings
    self._canvas_dimensions: tuple[int, int] = canvas_dimensions or (1080, 1920)  # NEW

    # ... presets / http_client unchanged ...

    self._preprocessor = ImagePreprocessor(final_dimensions=self._canvas_dimensions)  # NEW
    self._composer = PosterComposer(canvas_width=self._canvas_dimensions[0])          # NEW
    self._rasterizer = Rasterizer(
        width=self._canvas_dimensions[0],
        height=self._canvas_dimensions[1],
    )                                                                                  # NEW

# at FlyerOutput construction:
return FlyerOutput(
    png_bytes=png_bytes,
    dimensions=self._canvas_dimensions,  # was (1080, 1920)
    ...
)
```

### `preprocessor.py::ImagePreprocessor`

```python
class ImagePreprocessor:
    SOURCE_DIMENSIONS = (832, 1472)
    FINAL_DIMENSIONS = (1080, 1920)  # back-compat default kept for introspection

    def __init__(self, final_dimensions: tuple[int, int] = (1080, 1920)) -> None:  # NEW
        self._final_dimensions = final_dimensions

    def upscale(self, raw_bytes: bytes, comfy_job: ComfyJob) -> GeneratedBackground:
        img = Image.open(io.BytesIO(raw_bytes))
        resized = img.resize(self._final_dimensions, Image.Resampling.LANCZOS)  # was self.FINAL_DIMENSIONS
        # ... return GeneratedBackground(final_dimensions=self._final_dimensions, ...)
```

### `composer.py` — module + PosterComposer

```python
# Module-level (renamed from _CANVAS_WIDTH / _MARGIN_PX):
_DESIGN_CANVAS_WIDTH = 1080
_DESIGN_CANVAS_HEIGHT = 1920
_DESIGN_MARGIN_PX = 60

# _title_params() gains canvas_width / margin_px kwargs (back-compat defaults).

class PosterComposer:
    def __init__(self, canvas_width: int = 1080) -> None:  # NEW
        self._canvas_width = canvas_width
        self._margin_px = round(canvas_width * _DESIGN_MARGIN_PX / _DESIGN_CANVAS_WIDTH)
        self._canvas_height = round(canvas_width * _DESIGN_CANVAS_HEIGHT / _DESIGN_CANVAS_WIDTH)
        self._scale = canvas_width / _DESIGN_CANVAS_WIDTH

# In _build_svg, the outer <svg> changes from a hardcoded 1080×1920 to:
#     f'width="{self._canvas_width}" height="{self._canvas_height}" '
#     f'viewBox="0 0 {_DESIGN_CANVAS_WIDTH} {_DESIGN_CANVAS_HEIGHT}">'
# All interior SVG coords (zones, scrim positions, accent stripe, bg image,
# org credit) stay design-grid 1080×1920 — preserving byte-identical output
# at canvas_width=1080 and letting cairosvg's output_width/output_height
# (controlled by Rasterizer.__init__) drive the final raster dimensions.
```

## Test Counts

| Suite                                                | Pass | Failed | Notes                                       |
| ---------------------------------------------------- | ---: | -----: | ------------------------------------------- |
| New: `tests/unit/test_preprocessor_canvas_dimensions.py` |   5 |      0 | Default + 3 poster sizes                    |
| New: `tests/unit/test_composer_canvas_dimensions.py`     |  10 |      0 | Constructor, margin scaling, SVG width attr |
| New: `tests/test_pipeline_canvas_dimensions.py`          |  10 |      0 | Threading + e2e dimensions                  |
| Existing `tests/test_composer.py`                        |  21 |      0 | No regression                               |
| Existing `tests/unit/test_composer_template_driven.py`   |  16 |      0 | No regression                               |
| Existing `tests/test_layout.py`                          |  14 |      0 | No regression                               |
| Existing `tests/test_preprocessor.py`                    |   7 |      0 | No regression                               |
| Existing `tests/test_pipeline.py`                        |   6 |      0 | No regression                               |
| Existing `tests/api/test_worker_tasks.py`                |  20 |      0 | Flyer worker call site unchanged            |
| Existing `tests/api/test_flyer_e2e_permutations.py`      |  21 |      0 | Subtype × template permutations unchanged   |
| **Full suite (excluding `slow` + `tests/integration`)**  | **1619** | **0** | Zero regression                            |

## Back-compat Verification

```bash
$ grep -n "canvas_dimensions" flyer_generator/pipeline.py | head -3
41:    ``canvas_dimensions: tuple[int, int]`` keyword. When ``None`` (default),
57:        canvas_dimensions: tuple[int, int] | None = None,
63:        self._canvas_dimensions: tuple[int, int] = canvas_dimensions or (1080, 1920)
```
=> kwarg + assignment + threading present (≥3 lines).

```bash
$ grep -cn "^_CANVAS_WIDTH = 1080" flyer_generator/stages/composer.py
0
```
=> module-level `_CANVAS_WIDTH` constant removed.

```bash
$ grep -n "FINAL_DIMENSIONS" flyer_generator/stages/preprocessor.py
25:    FINAL_DIMENSIONS = (1080, 1920)
```
=> only back-compat class-level default; call site uses `self._final_dimensions`.

```bash
$ .venv/bin/python -m pytest tests/api/test_worker_tasks.py tests/api/test_flyer_e2e_permutations.py -q
.................................. [100%]  41 passed
```
=> existing flyer worker behavior unchanged (no kwarg → `(1080, 1920)` PNG).

## Deviations from Plan

None. The plan executed as written. Two minor implementation refinements within the planned approach:

1. **Module-level constants renamed, not removed.** The plan said "remove module-level `_CANVAS_WIDTH = 1080` and `_MARGIN_PX = 60`." I renamed them to `_DESIGN_CANVAS_WIDTH = 1080`, `_DESIGN_CANVAS_HEIGHT = 1920`, `_DESIGN_MARGIN_PX = 60` to mark them as the *design coordinate system* (used by `_title_params`'s default kwargs and by interior SVG coord clamping) — distinct from the *runtime canvas* on the instance. The plan's `test_existing_module_constants_removed_or_unused` was designed to catch the original names; my tests assert `not hasattr(composer_module, "_CANVAS_WIDTH")` and `not hasattr(composer_module, "_MARGIN_PX")` which still hold (the original names are gone).
2. **SVG viewBox stays in design-grid coords.** The plan's interface block suggested scaling everything proportionally inside the SVG. I kept `viewBox="0 0 1080 1920"` and only scaled the outer `<svg width="..." height="...">` attributes, because cairosvg's `output_width` / `output_height` (set by `Rasterizer.__init__`) drives the raster size regardless. This is a strictly safer change (zero diff at `canvas_width=1080`) and it isolates the per-stage dimension responsibility: `Rasterizer` is the source of truth for raster pixel size, `PosterComposer` just emits SVG that fits its design grid. If a future plan needs design-grid scaling (e.g. larger zone coords for a properly-laid-out 5400-wide poster), it can be added without changing this contract.

## Verification Commands

```bash
.venv/bin/python -m pytest tests/test_pipeline_canvas_dimensions.py \
  tests/unit/test_preprocessor_canvas_dimensions.py \
  tests/unit/test_composer_canvas_dimensions.py -v
# 25 passed

.venv/bin/python -m pytest tests/test_pipeline.py tests/test_composer.py \
  tests/unit/test_composer_template_driven.py tests/test_layout.py \
  tests/test_preprocessor.py -v
# 64 passed (no regression)

.venv/bin/python -m pytest tests/api/test_worker_tasks.py \
  tests/api/test_flyer_e2e_permutations.py -v
# 41 passed (existing flyer worker behavior unchanged)

.venv/bin/python -m pytest tests/ -q -k "not slow" --ignore=tests/integration
# 1619 passed, 2 deselected, 2 warnings in 103.78s
```

## Self-Check: PASSED

- [x] `flyer_generator/pipeline.py` exists and contains `canvas_dimensions` keyword-only kwarg.
- [x] `flyer_generator/stages/preprocessor.py` exists and accepts `final_dimensions` kwarg.
- [x] `flyer_generator/stages/composer.py` exists and accepts `canvas_width` kwarg; module-level `_CANVAS_WIDTH` / `_MARGIN_PX` removed.
- [x] `tests/unit/test_preprocessor_canvas_dimensions.py` exists (5 tests pass).
- [x] `tests/unit/test_composer_canvas_dimensions.py` exists (10 tests pass).
- [x] `tests/test_pipeline_canvas_dimensions.py` exists (10 tests pass).
- [x] Commit `3e26ffa` (Task 1 RED) found in git log.
- [x] Commit `15c8eb1` (Task 1 GREEN) found in git log.
- [x] Commit `6e2bc3f` (Task 2 RED) found in git log.
- [x] Commit `645481a` (Task 2 GREEN) found in git log.

## TDD Gate Compliance

The plan declares `type: tdd`. All 4 commit-pair gates exist in order:

- Task 1 RED  (`test(24-02): ...`) → `3e26ffa`
- Task 1 GREEN (`feat(24-02): ...`) → `15c8eb1`
- Task 2 RED  (`test(24-02): ...`) → `6e2bc3f`
- Task 2 GREEN (`feat(24-02): ...`) → `645481a`

No REFACTOR commit was needed — both GREEN implementations were minimal and clean on first pass.
