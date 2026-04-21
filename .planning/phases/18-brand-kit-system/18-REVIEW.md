---
phase: 18-brand-kit-system
reviewed: 2026-04-20T00:00:00Z
depth: standard
files_reviewed: 15
files_reviewed_list:
  - flyer_generator/brand_kit/__init__.py
  - flyer_generator/brand_kit/__main__.py
  - flyer_generator/brand_kit/applier.py
  - flyer_generator/brand_kit/audit.py
  - flyer_generator/brand_kit/contrast.py
  - flyer_generator/brand_kit/models.py
  - flyer_generator/brand_kit/palette.py
  - flyer_generator/brand_kit/scraper.py
  - flyer_generator/brand_kit/scraper_bs4.py
  - flyer_generator/brand_kit/scraper_playwright.py
  - flyer_generator/brand_kit/storage.py
  - flyer_generator/brochure/schema_renderer/__main__.py
  - flyer_generator/config.py
  - flyer_generator/errors.py
  - pyproject.toml
findings:
  critical: 0
  warning: 2
  info: 7
  total: 9
status: issues
---

# Phase 18: Code Review Report

**Reviewed:** 2026-04-20
**Depth:** standard
**Files Reviewed:** 15
**Status:** issues_found (advisory — does not block phase completion)

## Summary

The Phase-18 brand-kit subsystem is well-structured and demonstrates careful
attention to the review focus areas. Security gating is comprehensive:

- **SSRF:** `_is_safe_url` is applied at all three attack surfaces (entry URL
  in `fetch_brand_kit`, stylesheet URLs inside `scrape_bs4` via lazy import
  to break the cycle, and logo URLs before `_download_logo`). Covers
  RFC1918, loopback, link-local, multicast, reserved, unspecified, plus
  `localhost` hostname variants.
- **Path traversal:** Multiple containment checks: `storage._validate_containment`
  (CWD/HOME + explicit override), `applier._load_primary_logo_bytes`
  (`candidate.relative_to(kit_dir)`), `_download_logo` (pre- and post-fetch
  `dest.parent` check), plus slug regex `^[a-z0-9][a-z0-9-]*$`.
- **Size caps:** `_MAX_ASSET_BYTES=20MB` per-asset, `_MAX_TOTAL_BYTES=50MB`
  aggregate, `_MAX_IMAGE_MP=50M` pixel cap on rendered PNGs in audit.
- **`FLYER_BRAND_KITS_ALLOW_SYSTEM`:** Not silently bypassed — enforced
  only when resolving from `Settings()` (env-driven path); explicit
  `base_dir=` kwargs are treated as caller-trusted (documented in
  `resolve_kit_dir` docstring).

Correctness invariants are also generally sound: `apply_brand_kit(template,
kit)` arg order is called correctly in `remediate_contrast` (and a comment
marks the regression site); `wcag_ratio` routes every call through
`_hex_to_floats` (the known 0-255-vs-0.0-1.0 pitfall is avoided);
`BrandKit.palette / typography / voice / photography` are all `| None`;
`coloraide` usage in `_oklch_lightness_search` correctly does
`Color(hex).convert("oklch")` and mutates `c["lightness"]`.

Pydantic v2 discipline is consistent: every model uses
`ConfigDict(extra="forbid")`, no deprecated `class Config:` patterns,
`@field_validator` decorators on hex fields, `Field(default_factory=...)`
for collections. CLI semantics match the CONTEXT spec
(`--brand-kit` overrides `--color-accent` with stderr warning; explicit
`--logo` wins over kit logo).

Findings below are all **advisory**. Two warnings describe genuine
reachability/data-flow concerns; the info items are tech-debt-level nits.

## Warnings

### WR-01: Density-only audit results never invoke `remediate_density`

**File:** `flyer_generator/brand_kit/audit.py:101-106` (+ `iterate_audit_loop` at 620-641)
**Issue:** `AuditReport.is_clean` returns `True` when the only issues are
`severity="info"` (and contrast passes). Density issues are emitted with
`severity="info"` (line 388). The loop in `iterate_audit_loop` short-circuits
on `report.is_clean` (line 626), so a report with *only* density issues
converges on cycle 0 and `remediate_density` is never called — even when
`regenerate_fn` is provided.

This means the W10b density-remediation path is effectively unreachable
via the default composite loop. The only way it fires is if a contrast
failure is *also* present in the same cycle (pulling `is_clean` to `False`),
at which point the composite calls both remediations.

Re-read the behaviour in the composite (`_make_default_remediate._composite`,
lines 550-569): it does correctly gate on `audit.issues` (line 560-563),
so the remediation code itself is right; the unreachability is in the
convergence predicate.

**Fix:** Either (a) raise density issues that should drive regen to
`severity="warn"` so `is_clean` returns `False`, or (b) change
`iterate_audit_loop`'s convergence check to also test for outstanding
density issues when `regenerate_fn` is available. Example of (a):

```python
# audit.py ~line 385
if fill < _DENSITY_LOW_THRESHOLD:
    issues.append(
        AuditIssue(
            severity="warn",  # was "info" — drives iteration
            category="density",
            ...
        )
    )
```

If the Phase-18 scope really wants density to be advisory only (never
trigger regen), keep severity `"info"` and remove the `remediate_density`
composition from `_make_default_remediate` to avoid the false affordance.

---

### WR-02: `_bs4_to_palette` accepts raw CSS variable values that may be malformed hex

**File:** `flyer_generator/brand_kit/scraper.py:187-215`
**Issue:** `_bs4_to_palette` pulls CSS custom-property values
directly out of `artifacts.css_color_vars` and feeds them to
`ColorUsage(hex=...)`. The upstream filter in `scraper_bs4.py:179` accepts
values whose length is 4, 7, or 9 (`#RGB`, `#RRGGBB`, `#RRGGBBAA`), but
`validate_hex_color` enforces `^#[0-9A-Fa-f]{6}$` — anything not exactly
6 digits raises `ValueError`.

The `try/except Exception` at lines 205/214 catches the failure and
returns `None`, which is correct for safety — but:

1. The caller silently loses the palette (falls through to `None`), so
   what looked like a successful BS4 extraction yields no palette.
2. The swallowed exception is not logged — debugging why a kit has
   `palette=None` becomes painful.
3. A site using `#abc` 3-digit shorthand for its brand color will always
   fail this path.

**Fix:** Either expand the CSS-var filter to normalize 3-digit → 6-digit
hex before accepting the value, or log the rejection:

```python
try:
    return BrandPalette(...)
except Exception as err:  # noqa: BLE001
    logger.warning("bs4_palette_build_failed", error=str(err))
    return None
```

And/or add a normalization step in `scraper_bs4.py` around line 179:

```python
if val.startswith("#") and len(val) == 4:
    # Expand #abc -> #aabbcc
    val = "#" + "".join(c * 2 for c in val[1:])
if val.startswith("#") and len(val) == 7:
    css_color_vars[d.name] = val
```

---

## Info

### IN-01: `_download_logo` containment check uses `dest.parent`, not `kit_dir`

**File:** `flyer_generator/brand_kit/scraper.py:124-135, 150-156`
**Issue:** The path-traversal guard resolves `dest` and `dest.parent`
and verifies `target.relative_to(parent)`. Since `dest.parent` is
`kit_dir/logos`, this only protects the *logos subdirectory*, not
`kit_dir` itself. If `_safe_logo_filename` ever leaked a sanitized-but-
still-special name, an escape to a sibling of `logos/` would slip past
this guard. It currently works because `_safe_logo_filename` aggressively
sanitizes (strips `..`, `/`, etc.), but the guard's contract is weaker
than the prose comment "W9: containment guard" suggests.

**Fix (low urgency):** Resolve against `kit_dir` rather than `dest.parent`,
matching how `applier._load_primary_logo_bytes` does it:

```python
kit_dir = dest.parents[1].resolve()  # .../<kit>/logos -> .../<kit>
target = dest.resolve()
target.relative_to(kit_dir)
```

---

### IN-02: `BrandKitContrastError` is declared but never raised

**File:** `flyer_generator/errors.py:84-85` (+ `contrast.py:12` comment promising escalation)
**Issue:** `BrandKitContrastError` is part of the public error hierarchy
but no production code path raises it. `remediate()` returns
`(fg, "FAIL: no AA-compliant fg found")` and leaves escalation to callers,
yet no caller in the subsystem actually escalates. The docstring at
`contrast.py:11-13` explicitly says the caller decides, so this is
intentional — but the class sits as dead hook-code until a caller opts in.

**Fix:** Either document in `errors.py` that this is a reserved-for-future
hook (similar to `UnknownPresetError`), or add a `strict=` mode to
`ensure_aa` / `remediate` that raises when exhausted. The test
`tests/brand_kit/test_errors.py:38` asserts it can be instantiated — no
behavioural coverage.

---

### IN-03: Every scraped logo is labeled `variant="primary"` regardless of source

**File:** `flyer_generator/brand_kit/scraper.py:176-181`
**Issue:** `_download_logo` hardcodes `variant="primary"`. When the scraper
finds multiple logos (header + alt mono versions), they all come back as
`"primary"`, defeating the `Literal["primary", "mono_dark", "mono_light",
"mark_only"]` contract's intent.

The applier's `next((lg for lg in kit.logos if lg.variant == "primary"),
kit.logos[0])` then matches the first one found, which is usually
acceptable — but the variant field carries no real information.

**Fix:** Either cap at one logo (the scraper already breaks at 3, but only
the first survives anyway), or infer variant from filename/context
heuristics, or document this as a Phase-18 simplification to be revisited.

---

### IN-04: `_download_logo` always writes `aspect_ratio=1.0`

**File:** `flyer_generator/brand_kit/scraper.py:180`
**Issue:** The `BrandLogo.aspect_ratio` field is a `Field(gt=0.0)` contract,
but the scraper never measures the actual image dimensions to compute it.
Downstream consumers that rely on aspect ratio (e.g. for placement logic)
get a wrong value for any non-square logo.

**Fix:** Add a `Pillow.Image.open(BytesIO(content)).size` call after
the size-cap check and store `w / h`. SVGs can parse `viewBox` or fall
back to `1.0` with a logged note.

```python
try:
    with Image.open(BytesIO(content)) as im:
        w, h = im.size
    aspect = w / max(1, h)
except Exception:
    aspect = 1.0
```

---

### IN-05: `audit._panel_crop_rect` assumes a rigid 3-panel horizontal layout

**File:** `flyer_generator/brand_kit/audit.py:175-191`
**Issue:** The crop-rect math does `panel_w = sheet_w // 3` and treats
every sheet as three equal horizontal panels in one of two fixed orders
(`_OUTSIDE_ORDER`, `_INSIDE_ORDER`). Any template whose panels don't
line up on thirds (e.g. asymmetric tri-fold with a narrow tuck flap) will
be mis-cropped, which flows into wrong whitespace ratios. The
CONTEXT.md notes `tuck_flap` is "typically a narrow filled accent panel"
— this file acknowledges that by skipping its warning emission (line 309),
but the *measurement* is still wrong.

**Fix:** Read the actual panel geometry from the template schema
(if available) rather than hard-coding `sheet_w // 3`. Alternatively,
document this approximation loudly — the module docstring at lines 7-16
mentions the shape-stacking simplification but not the panel-split one.

---

### IN-06: `type: ignore[arg-type]` at `scraper.py:179` hides a real type mismatch

**File:** `flyer_generator/brand_kit/scraper.py:173-179`
**Issue:** `fmt: str` is computed conditionally then passed to
`BrandLogo(... format=fmt)` which requires `Literal["png", "jpg", "svg"]`.
The `# type: ignore[arg-type]` papers over the fact that pyright can't
narrow `fmt` to the literal type. If the detection logic ever grows a
branch that produces `"gif"` or similar, it will slip past typecheck.

**Fix:** Use a `Literal["png", "jpg", "svg"]`-typed variable or a
`Final` assignment tree:

```python
fmt: Literal["png", "jpg", "svg"]
if url.lower().endswith(".svg") or content[:4] == b"<svg" or b"<svg " in content[:128]:
    fmt = "svg"
elif content[:3] == b"\xff\xd8\xff":
    fmt = "jpg"
else:
    fmt = "png"
```

Then the `type: ignore` can be removed.

---

### IN-07: `_bs4_to_palette` returns `None` on Pydantic failure without logging

**File:** `flyer_generator/brand_kit/scraper.py:214-215`
**Issue:** The bare `except Exception: return None` swallows any
construction failure silently. Related to WR-02 but specifically the
absent logging means operators see `palette=None` on a kit and have no
trail to explain it.

**Fix:** Add a `log.warning("bs4_to_palette_build_failed", error=str(err))`
— the orchestrator passes `log` through `_palette_from_screenshot` but
not through `_bs4_to_palette`. Thread the logger or fall back to the
module-level `logger`.

---

_Reviewed: 2026-04-20_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
