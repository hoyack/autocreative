---
phase: 24-poster-primitive
reviewed: 2026-04-25T00:00:00Z
depth: standard
files_reviewed: 36
files_reviewed_list:
  - alembic/versions/f24t01_poster_primitive.py
  - flyer_generator/api/models/__init__.py
  - flyer_generator/api/models/job.py
  - flyer_generator/api/models/poster.py
  - flyer_generator/api/models/render.py
  - flyer_generator/api/routes/__init__.py
  - flyer_generator/api/routes/posters.py
  - flyer_generator/api/schemas/__init__.py
  - flyer_generator/api/schemas/posters.py
  - flyer_generator/api/tasks/__init__.py
  - flyer_generator/api/tasks/poster.py
  - flyer_generator/pipeline.py
  - flyer_generator/poster/__init__.py
  - flyer_generator/poster/schema_renderer/__init__.py
  - flyer_generator/poster/schema_renderer/loader.py
  - flyer_generator/poster/schema_renderer/schema_model.py
  - flyer_generator/poster/schemas/bold_announcement.json
  - flyer_generator/poster/schemas/cinematic_onesheet.json
  - flyer_generator/poster/schemas/editorial_grand.json
  - flyer_generator/stages/composer.py
  - flyer_generator/stages/preprocessor.py
  - frontend/src/api/client.ts
  - frontend/src/api/openapi.snapshot.json
  - frontend/src/api/schema.gen.ts
  - frontend/src/components/DashboardLayout.tsx
  - frontend/src/pages/jobs/list.tsx
  - frontend/src/pages/posters/new.test.tsx
  - frontend/src/pages/posters/new.tsx
  - frontend/src/pages/posters/status.tsx
  - frontend/src/pages/renders/gallery.tsx
  - frontend/src/routes.tsx
  - tests/api/test_migrations_poster.py
  - tests/api/test_poster_models_ddl.py
  - tests/api/test_poster_permutations.py
  - tests/api/test_poster_routes.py
  - tests/api/test_poster_schemas.py
  - tests/api/test_worker_poster_tasks.py
  - tests/poster/__init__.py
  - tests/poster/schema_renderer/__init__.py
  - tests/poster/schema_renderer/test_loader.py
  - tests/poster/schema_renderer/test_schema_model.py
  - tests/poster/test_render_smoke.py
  - tests/test_pipeline_canvas_dimensions.py
  - tests/unit/test_composer_canvas_dimensions.py
  - tests/unit/test_preprocessor_canvas_dimensions.py
findings:
  critical: 0
  warning: 5
  info: 6
  total: 11
status: issues_found
---

# Phase 24: Code Review Report

**Reviewed:** 2026-04-25
**Depth:** standard
**Files Reviewed:** 45 (some listed entries are empty `__init__.py` markers; full set above)
**Status:** issues_found

## Summary

Phase 24 ships the "poster primitive" — a parallel-id `PosterRecord`, a `POST /api/v1/posters` route with compensating-enqueue, an arq worker that re-uses `FlyerGenerator` at injected canvas dimensions (5400×7200, 7200×10800, 8100×12000), three JSON template schemas, and the React page + status flow. Test coverage is thorough: schema permutations, migration up/down, parallel-id contract, path-traversal guard, compensating-enqueue with no-secret-leak grep, render-smoke at all 9 (template × size) permutations.

Security-wise the implementation matches Phase 22/23 patterns precisely: explicit `extra="forbid"`, `Literal` size enum at the schema layer, defense-in-depth `_size_to_canvas_dimensions` and `_validate_template_slug` at the worker, `{"reason","type"}`-only `error_detail` (no `str(exc)` leak), and React-escaped JSX renders only — no `dangerouslySetInnerHTML`.

The five warnings below are not security bugs but design/correctness concerns worth confirming before shipping:
1. **The composer ignores the template's `panels` structure entirely** — the rich shape/text/image elements defined in each shipped JSON are never rendered, only typography + palette + cover_title_size. This contradicts the template files' apparent intent.
2. **`_build_flyer_input` maps `brand_kit_slug` to `FlyerInput.org`** — the poster's bottom credit will read "Presented by acme-co" (the slug), not the brand's display name.
3. **When no `subheading` is supplied, `description` falls back to `headline`** — duplicating the title text into the info-description block.
4. **`load_template` still accepts arbitrary `.json` paths** — the worker guards against this, but other callers of the public loader API can bypass that guard.
5. **Compensating-enqueue uses `request.app.state.sessionmaker`** without an existence check — if the attribute is absent the original `enqueue` exception is masked by `AttributeError`.

No `dangerouslySetInnerHTML`, hardcoded secrets, SQL string interpolation, `eval`, or unsafe deserialization were found. Empty test-package `__init__.py` files are intentional (PEP 420 alternative).

## Warnings

### WR-01: Composer ignores poster template `panels.hero.elements`

**File:** `flyer_generator/stages/composer.py:306-661` (entire `_build_svg`); `flyer_generator/poster/schemas/bold_announcement.json:24-49`; `flyer_generator/poster/schemas/cinematic_onesheet.json:24-39`; `flyer_generator/poster/schemas/editorial_grand.json:24-35`

**Issue:** Each shipped poster template JSON declares a richly populated `panels.hero.elements` array (image placeholders at `[0, 0, 5400, 7200]`, full-bleed scrim rects with linear gradients, accent stripes at specific `rect=[0, 6960, 5400, 40]` positions, role-tagged text elements with `bbox` + `content_key` + `letter_spacing`). However, `PosterComposer._build_svg` only consumes:

- `template.typography.heading_family` / `body_family`
- `template.typography.cover_title_size` / `body_size` / `body_line_height` / `body_max_chars_per_line`
- `template.palette.scrim_opacity_top` / `scrim_opacity_bottom`
- `template.palette.accent_default`

The `panels.hero.elements` list — including `editorial_grand`'s `"static_text": "ESTABLISHED"` static text and `cinematic_onesheet`'s 70/30 image+text-block split — is never read. The composer falls back to its hardcoded 1080×1920 design-grid layout (scrims at `y=0..700` / `y=1220..1920`, accent stripe at `y=1908`, org credit at `y=1840`) for every template. Tone differences between templates are reduced to font + color choices.

**Fix:** Either (a) add a panel-renderer pass that consumes `template.panels.hero.elements` (mirrors the brochure schema renderer pattern), or (b) drop the unused JSON fields from the shipped templates and from `PosterTemplateSchema.panels` so the schema reflects what the composer actually uses. Option (b) is the smaller change for v1:

```python
# flyer_generator/poster/schema_renderer/schema_model.py
class PosterTemplateSchema(BaseModel):
    # ... keep schema_version, name, description, tone_keywords,
    #     canvas, palette, typography
    # Drop the panels field until a poster-aware panel renderer ships;
    # the unused JSON elements imply functionality that doesn't exist.
```

Until one of these lands, the test `tests/poster/schema_renderer/test_loader.py::test_shipped_template_has_text_and_shape` is asserting structure that is never actually rendered, which can mislead future contributors.

---

### WR-02: `brand_kit_slug` is rendered as the org name in the poster credit line

**File:** `flyer_generator/api/tasks/poster.py:120-128` (`_build_flyer_input`); `flyer_generator/stages/composer.py:583-589` (org credit emission)

**Issue:** The worker maps the request's `brand_kit_slug` straight onto `FlyerInput.org`:

```python
org=payload.get("brand_kit_slug") or "",
```

`PosterComposer._build_svg` then renders:

```python
org_credit = (
    f'<text x="540" y="1840" ... >'
    f"Presented by {org_esc}</text>"
)
```

So a poster with `brand_kit_slug="acme-co"` ships with the literal text **"Presented by acme-co"** in the bottom credit. Slugs are intended for URL routing, not display.

The docstring already calls this out as "placeholder; future plan may surface a brand_kit-derived org name" but it is shipping in v1 user-visible output.

**Fix:** Either resolve the brand kit's display name before building `FlyerInput`, or render an empty credit when no display name is available:

```python
# Option A — lookup display name from brand_kits table
async def _resolve_org_name(sessionmaker, slug: str | None) -> str:
    if not slug:
        return ""
    async with sessionmaker() as s:
        bk = await s.get(BrandKitRecord, slug)
        return bk.display_name if bk else ""

# Option B — drop org from posters; poster credits are templatable
return FlyerInput(
    title=payload["headline"],
    subtype="info",
    ...
    org="",  # poster credit handled by template, not slug-substituted
    ...
)
```

---

### WR-03: `description` silently duplicates `headline` when no `subheading` is provided

**File:** `flyer_generator/api/tasks/poster.py:120-128` (`_build_flyer_input`)

**Issue:** When the user submits a poster with no `subheading`, the worker substitutes the headline:

```python
description=payload.get("subheading") or payload["headline"],
```

The composer's `_build_info_description_elements` then renders the headline a second time as the info-flyer description block (below the title, in body typography). The user-visible result is a poster whose title text appears twice — once oversized at the top, once again as a paragraph below. The same pattern applies to `style_concept`:

```python
style_concept=payload.get("image_hint") or payload["headline"],
```

For `style_concept` this is mostly fine (it seeds the Comfy prompt and is internal), but the `description` duplication is user-visible.

**Fix:** Pass `None` when no subheading is supplied; let the composer's `_build_info_description_elements` no-op naturally (`if not description_esc and not cta_esc: return []`):

```python
return FlyerInput(
    title=payload["headline"],
    subtype="info",
    description=payload.get("subheading"),  # may be None — composer handles it
    call_to_action=payload.get("cta_text"),
    org=payload.get("brand_kit_slug") or "",
    style_concept=payload.get("image_hint") or payload["headline"],  # ok — Comfy prompt seed
    style_preset=payload["style_preset"],
)
```

Confirm `FlyerInput.description: str | None` already permits None on the info subtype (per its Phase 22 plan-02 relaxation). If the field is required-non-empty, set it to `""` instead and adjust the composer's emptiness check.

---

### WR-04: `load_template` accepts arbitrary file paths from any caller

**File:** `flyer_generator/poster/schema_renderer/loader.py:13-32`

**Issue:** The loader's "convenience" branch will read any `.json` path on the filesystem when the input ends in `.json`:

```python
if name_or_path.endswith(".json"):
    path = Path(name_or_path)
else:
    path = _SCHEMAS_DIR / f"{name_or_path}.json"
```

The worker guards against this in `_validate_template_slug` (T-24-08), and `PosterCreateRequest.template` enforces `max_length=64`, so the public POST route is safe. But `load_template` is exported from `flyer_generator.poster.schema_renderer` and is reachable by:

- A future internal caller (e.g. CLI, a brochure-style admin script) that forgets to call the worker's slug guard.
- A future consumer importing the public API and passing user input directly.

If any such caller passes attacker-controlled input, the `.endswith(".json")` branch happily reads `Path("/etc/secret.json")` (or any path the process can read).

**Fix:** Move the slug-vs-path enforcement into `load_template` itself so the guard cannot be forgotten. The loader is the right place for the security boundary:

```python
def load_template(name: str) -> PosterTemplateSchema:
    """Load a poster template schema by bare slug. Path-like names rejected."""
    if name.endswith(".json") or "/" in name or "\\" in name:
        raise ValueError(
            "template must be a bare slug, not a path "
            "(no '.json' suffix, no '/' or '\\\\' separators)"
        )
    path = _SCHEMAS_DIR / f"{name}.json"
    if not path.exists():
        raise FileNotFoundError(
            f"Schema template not found: {name}. Available: {list_templates()}"
        )
    return PosterTemplateSchema.model_validate(json.loads(path.read_text(encoding="utf-8")))
```

If the existing path-loading capability is needed by tests (e.g. `tests/poster/schema_renderer/test_loader.py::test_load_by_path`), expose it under a separate explicitly-internal helper:

```python
def _load_template_from_path(path: Path) -> PosterTemplateSchema:
    """Internal: load by absolute path. NEVER call with untrusted input."""
    return PosterTemplateSchema.model_validate(
        json.loads(path.read_text(encoding="utf-8"))
    )
```

This is defense-in-depth — the worker's existing guard is correct — but the public loader contract is the better place to enforce it.

---

### WR-05: Compensating-enqueue assumes `request.app.state.sessionmaker` exists; raises `AttributeError` masking original exception when absent

**File:** `flyer_generator/api/routes/posters.py:60-78`

**Issue:** The compensating-enqueue path opens a fresh session via `request.app.state.sessionmaker()`:

```python
except Exception as exc:
    async with request.app.state.sessionmaker() as s2:
        row = await s2.get(JobRecord, job_id)
        ...
    raise
```

If `request.app.state.sessionmaker` is missing or has been swapped for an unexpected type, the `except` body raises an `AttributeError` (or whatever the descriptor raises) which then propagates instead of the original `exc`. The original failure context (the arq enqueue exception) is lost — both for the client (sees a generic 500 with the wrong cause) and for the operator (the structlog stacktrace points at the AttributeError, not the Redis failure).

This is consistent with the postcard route pattern that this file mirrors, so the issue is broader than poster-specific. But it should be reviewed.

**Fix:** Wrap the compensating block defensively so the original exception always wins:

```python
except Exception as exc:
    try:
        sessionmaker = getattr(request.app.state, "sessionmaker", None)
        if sessionmaker is not None:
            async with sessionmaker() as s2:
                row = await s2.get(JobRecord, job_id)
                if row is not None:
                    row.status = JobStatus.FAILED
                    row.error_detail = {
                        "reason": "enqueue_failed",
                        "type": type(exc).__name__,
                    }
                    await s2.commit()
    except Exception:
        # Compensation itself failed — log and swallow; the original
        # arq exception is still propagated below so the client + the
        # structlog trace point at the real cause.
        logger.exception("compensating_enqueue_failed", job_id=job_id)
    raise
```

If this pattern is universal across primitives (postcards, brochures, posters), consider extracting a shared `_compensate_enqueue_failure` helper.

## Info

### IN-01: `frontend/src/api/openapi.snapshot.json` is a generated artifact tracked in git

**File:** `frontend/src/api/openapi.snapshot.json` (2789 lines)

**Issue:** This file is the FastAPI-emitted OpenAPI document, captured at build time so the typescript schema generator (`schema.gen.ts`) has a stable input. It is generated, large, and was included in the review set.

**Fix:** Either (a) move it to a `generated/` subtree and exclude from review, or (b) keep but add a header comment marking it as generated so future reviewers skip it. No action required for this phase.

---

### IN-02: Posters reuse `artifact_root_flyer` rather than introducing `artifact_root_poster`

**File:** `flyer_generator/api/tasks/poster.py:194-198`

**Issue:** Poster output lives at `<artifact_root_flyer>/posters/<job_id>.png`. The existing flyer worker writes to `<artifact_root_flyer>/<job_id>.png`. Namespacing by sub-directory is fine for collision avoidance, but operators reading the `Settings` env contract may expect a parallel `FLYER_ARTIFACT_ROOT_POSTER` variable to appear alongside `FLYER_ARTIFACT_ROOT_BROCHURE` and the social-campaign roots.

**Fix:** Either accept the chosen pattern (CONTEXT.md "Claude's discretion" already covers this), or add a new `artifact_root_poster: Path` setting field defaulting to `<artifact_root_flyer>/posters` so the path is configurable by env var without code changes. No action required.

---

### IN-03: `_size_to_canvas_dimensions` raises `ValueError` for unknown size, but the route already returns 422 for that case

**File:** `flyer_generator/api/tasks/poster.py:62-76`

**Issue:** `_size_to_canvas_dimensions` is correctly implemented as defense-in-depth (T-24-14) — even though `size: Literal["18x24","24x36","27x40"]` already prevents bad values from reaching the worker, the worker still validates. The test `tests/api/test_worker_poster_tasks.py::test_task_bogus_size_raises_and_marks_failed` exercises this path by calling the worker directly with `size="36x48"`. This is the right pattern — flagging only as an observation that the dual-layer validation is intentional.

**Fix:** None. The pattern is correct; documenting here so future "DRY this up" refactors know to keep both layers.

---

### IN-04: Generated job IDs in worker tests use `[:26]` slicing of strings that may not be 26 chars

**File:** `tests/api/test_worker_poster_tasks.py:209,256,286,327,362,393,423,455,480,521,560`

**Issue:** Job IDs in tests are constructed like:

```python
jid = "01HPOSTER0000000000000018X24"[:26]
```

The string is 28 characters, sliced to 26 — fine. But this is fragile: a future contributor renaming the suffix (e.g. swapping `18X24` for `S18X24`) may not realize the slice is required, producing a job ID that violates the 26-char ULID column constraint. The constraint failure would surface at `s.commit()` in the seed step, not at the slice itself.

**Fix:** Use a helper to generate test job IDs from a label:

```python
def _test_job_id(label: str) -> str:
    """Build a 26-char placeholder ULID from a label, padding with '0'."""
    return (label + "0" * 26)[:26]
```

Or simply use `str(ulid.ULID())` if a real ULID is acceptable.

---

### IN-05: `_select_layout_variant` heuristic only fires for event flyers; info-subtype variant selection is duplicated inline

**File:** `flyer_generator/stages/composer.py:163-175,442-456`

**Issue:** `_select_layout_variant(title_row, details_row, title_col)` is a clean helper, but the info-subtype path duplicates the variant logic inline:

```python
if title_col == "LEFT":
    layout_variant = "sidebar"
elif title_row == "TOP" and title_col == "CENTER":
    layout_variant = "centered"
else:
    layout_variant = "minimal"
```

This is a pre-existing pattern from Phase 22 (composer was unchanged in scope here), but the duplication is now larger because info posters also flow through this branch.

**Fix:** Extract a `_select_info_layout_variant(title_row, title_col)` helper or extend `_select_layout_variant` to accept `details_row=None` and handle the info case in one place. Optional refactor.

---

### IN-06: `load_template`'s `FileNotFoundError` message embeds the resolved `path` — could leak the install root

**File:** `flyer_generator/poster/schema_renderer/loader.py:25-29`

**Issue:** When a template is not found, the loader raises:

```python
raise FileNotFoundError(
    f"Schema template not found: {path}. Available: {available}"
)
```

`path` is the absolute path it tried to read (e.g. `/home/runner/.../flyer_generator/poster/schemas/foo.json`). On the worker this exception's class name reaches the JSON `error_detail` column via `mark_failed`, which is correct (only `type(exc).__name__` is recorded — see `flyer_generator/api/tasks/_state.py` pattern). But if any caller logs `str(exc)` or surfaces it to a client, the install path leaks.

`mark_failed` in this codebase is already minimal (mirror of postcard worker), so the immediate impact is low. Worth keeping in mind for any future change that adds `str(exc)` to error responses.

**Fix:** Drop the absolute path from the message; show only the requested name:

```python
raise FileNotFoundError(
    f"Schema template not found: {name_or_path!r}. Available: {available}"
)
```

---

_Reviewed: 2026-04-25_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
