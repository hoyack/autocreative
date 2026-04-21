# Phase 19: Social Media Posting System - Pattern Map

**Mapped:** 2026-04-21
**Files analyzed:** 26 new + 4 modified
**Analogs found:** 30 / 30
**Phase 18 pattern-clone confidence:** HIGH (every Phase 19 module has a direct Phase 18 counterpart)

## File Classification

### New package files

| New/Modified File | Role | Data Flow | Closest Analog | Match |
|---|---|---|---|---|
| `flyer_generator/social/__init__.py` | package barrel export | n/a | `flyer_generator/brand_kit/__init__.py` | exact |
| `flyer_generator/social/__main__.py` | typer CLI | request-response | `flyer_generator/brand_kit/__main__.py` | exact |
| `flyer_generator/social/models.py` | Pydantic data contracts | n/a | `flyer_generator/brand_kit/models.py` | exact |
| `flyer_generator/social/generator.py` | single-post orchestrator | async compose | `flyer_generator/brochure/schema_renderer/text_gen.py::generate_content_from_prompt` + `flyer_generator/brand_kit/scraper.py::fetch_brand_kit` | role-match |
| `flyer_generator/social/campaign.py` | fan-out orchestrator | async fan-out | `flyer_generator/brochure/schema_renderer/image_gate.py::generate_template_images` | role-match |
| `flyer_generator/social/renderer.py` | SVG -> PNG + Pillow crop | transform | `flyer_generator/brochure/schema_renderer/renderer.py::render_schema_brochure` | role-match (simpler one-panel wrapper) |
| `flyer_generator/social/audit.py` | post-artifact audit | transform | `flyer_generator/brand_kit/audit.py::audit_render` | exact |
| `flyer_generator/social/storage.py` | filesystem I/O | file-I/O | `flyer_generator/brand_kit/storage.py` | exact (campaign_id adds one nesting level) |
| `flyer_generator/social/voice.py` | BrandVoice-aware prompt assembly | transform | `flyer_generator/brochure/schema_renderer/text_gen.py::_render_budget_prompt` / `_format_brief` | role-match |

### Platform rule registry

| File | Role | Analog | Match |
|---|---|---|---|
| `flyer_generator/social/platforms/linkedin.py` | rules + validator | `flyer_generator/brand_kit/contrast.py` (module-scope constants + pure-function validator pattern) | role-match |
| `flyer_generator/social/platforms/twitter.py` | rules + validator | same | role-match |
| `flyer_generator/social/platforms/instagram.py` | rules + validator | same | role-match |
| `flyer_generator/social/platforms/facebook.py` | rules + validator | same | role-match |
| `flyer_generator/social/platforms/__init__.py` | platform registry | `flyer_generator/brand_kit/__init__.py` | role-match |
| `flyer_generator/social/validation.py` (shared primitives) | pure validator | `flyer_generator/brand_kit/contrast.py::wcag_ratio` | role-match |
| `flyer_generator/social/readability.py` | pure stateless heuristic | `flyer_generator/brochure/schema_renderer/text_fit.py::chars_per_line` | role-match |

### Templates + schema

| File | Role | Analog | Match |
|---|---|---|---|
| `flyer_generator/social/schemas/schema_model.py` | Pydantic TemplateSchema | `flyer_generator/brochure/schema_renderer/schema_model.py` | exact (simpler, single-panel) |
| `flyer_generator/social/schemas/loader.py` | JSON -> PostTemplate | `flyer_generator/brochure/schema_renderer/loader.py` | exact |
| `flyer_generator/social/schemas/linkedin__announcement.json` (x12+) | template data | `flyer_generator/brochure/schemas/editorial_classic.json` | role-match |

### Modifications

| Modified File | Role | Analog (for shape of change) |
|---|---|---|
| `flyer_generator/brochure/schema_renderer/text_gen.py` | add `brand_voice` + `tighter_budgets` params | existing `generate_content_from_prompt` signature + `_SYSTEM_PROMPT` constant |
| `flyer_generator/errors.py` | add `SocialError` tree + `BrandVoiceViolationError` | existing `BrandKitError` / `BrandKitAuditError` subclass pattern |
| `.gitignore` | add `.social-campaigns/` | existing `.brand-kits/` line |
| `pyproject.toml` | add `python-ulid>=3.1.0` | existing brand_kit-era additions |
| `.social-template.json` (new, tracked) | reference schema | `.brand-kit-template.json` at repo root |
| `flyer_generator/config.py` | add `social_campaigns_dir: Path` + `FLYER_SOCIAL_CAMPAIGNS_DIR` | existing `brand_kits_dir` field |

### Tests (new)

| Test File | Analog |
|---|---|
| `tests/social/test_models.py` | `tests/brand_kit/test_models.py` |
| `tests/social/test_storage.py` | `tests/brand_kit/test_storage.py` |
| `tests/social/test_cli.py` | `tests/brand_kit/test_cli.py` |
| `tests/social/test_audit.py` | `tests/brand_kit/test_audit.py` |
| `tests/social/test_platforms_*.py` | `tests/brand_kit/test_contrast.py` |
| `tests/social/test_voice.py` | `tests/brand_kit/test_applier.py` |
| `tests/social/test_integration.py` | `tests/brand_kit/test_integration.py` |
| `tests/social/test_package_exports.py` | `tests/brand_kit/test_package_exports.py` |

---

## Pattern Assignments

### `flyer_generator/social/models.py` (Pydantic data contracts)

**Analog:** `flyer_generator/brand_kit/models.py`
**Why:** Phase 18's models file is the canonical Pydantic v2 + `ConfigDict(extra="forbid")` + nested-Optional pattern; Phase 19 models (PostSpec, Post, Campaign, PostBrief, PlatformRules, ValidationReport, ValidationIssue, Platform, Intent) share the same shape (top-level parent with optional nested children).

**Pattern to mirror** (lines 14-50, imports + ConfigDict + field_validator shape):
```python
from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from flyer_generator.brochure.models import validate_hex_color


class ColorUsage(BaseModel):
    """A single color with an optional semantic usage hint."""

    model_config = ConfigDict(extra="forbid")

    hex: str
    usage_hint: str | None = None

    @field_validator("hex")
    @classmethod
    def _validate_hex(cls, v: str) -> str:
        validated = validate_hex_color(v)
        return "#" + validated[1:].upper()
```

**Nested partial model pattern** (lines 100-114, BrandKit top-level with all-optional children):
```python
class BrandKit(BaseModel):
    """Top-level brand kit. Optional nested models allow partial scrapes."""

    model_config = ConfigDict(extra="forbid")

    name: str
    source_url: str | None = None
    fetched_at: datetime
    palette: BrandPalette | None = None
    typography: BrandTypography | None = None
    logos: list[BrandLogo] = Field(default_factory=list)
    voice: BrandVoice | None = None
    photography: BrandPhotoHints | None = None
    source_artifacts: list[str] = Field(default_factory=list)
    size_multiplier: float = Field(default=1.0, gt=0.0, le=3.0)
```

**Deviation:** Phase 19 introduces `Platform` and `Intent` as `Literal[...]` string-enums (not Pydantic Enum-class) to match the `_PanelName`/`_TextRole` style used in `schema_model.py` lines 19-46. Frozen models (`ConfigDict(frozen=True)`) for `PlatformRules` because rules are registry-singletons.

---

### `flyer_generator/social/storage.py` (filesystem I/O)

**Analog:** `flyer_generator/brand_kit/storage.py`
**Why:** CONTEXT.md §canonical_refs explicitly says "mirror exactly for `.social-campaigns/`". The slug regex, env-var resolution, containment guard, and lazy-import pattern transfer verbatim.

**Pattern to mirror** (lines 12-96, every element is load-bearing):
```python
from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import TYPE_CHECKING

from flyer_generator.config import Settings
from flyer_generator.errors import BrandKitError

if TYPE_CHECKING:  # pragma: no cover
    from flyer_generator.brand_kit.models import BrandKit

_SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")
_ALLOW_SYSTEM_ENV = "FLYER_BRAND_KITS_ALLOW_SYSTEM"


def _base_dir(base_dir: Path | None = None) -> Path:
    if base_dir is not None:
        return base_dir
    return Settings().brand_kits_dir


def _validate_slug(slug: str) -> None:
    if not _SLUG_RE.match(slug):
        raise BrandKitError(
            f"invalid slug {slug!r}: must match ^[a-z0-9][a-z0-9-]*$",
            slug=slug,
        )


def _validate_containment(kit_dir: Path, base: Path) -> None:
    if os.environ.get(_ALLOW_SYSTEM_ENV) == "1":
        return
    resolved = kit_dir.resolve()
    cwd = Path.cwd().resolve()
    home = Path.home().resolve()
    try:
        resolved.relative_to(cwd)
        return
    except ValueError:
        pass
    try:
        resolved.relative_to(home)
        return
    except ValueError:
        pass
    raise BrandKitError(
        "resolved brand-kit path is outside CWD and HOME; "
        f"set {_ALLOW_SYSTEM_ENV}=1 to override",
        resolved=str(resolved),
        base=str(base),
    )
```

**Deviation:** Phase 19 adds **one extra nesting level** for campaign_id:
- Brand kit: `<base>/<slug>/brand.json`
- Social: `<base>/<slug>/<campaign_id>/campaign.json` + `<platform>__<intent>/{post.json,image.png,audit.json}`

Expected changes: rename `_base_dir` to read `Settings().social_campaigns_dir`; rename env constant to `FLYER_SOCIAL_CAMPAIGNS_ALLOW_SYSTEM`; validate both `slug` AND `campaign_id` (ULID is a valid slug under the same regex, so `_SLUG_RE` is reusable). Add `resolve_campaign_dir(slug, campaign_id, ...)` that chains two `_validate_slug` calls. Raise `SocialError` instead of `BrandKitError`.

---

### `flyer_generator/social/__main__.py` (typer CLI)

**Analog:** `flyer_generator/brand_kit/__main__.py`
**Why:** Same typer shape — `app = typer.Typer(..., no_args_is_help=True)`, `Annotated[str, typer.Argument(...)]`, `typer.Exit(2)` on domain errors, `asyncio.run(...)` for async orchestrators.

**Pattern to mirror** (lines 1-55, the full Typer setup + one async command):
```python
"""Brand-kit CLI: `python -m flyer_generator.brand_kit {fetch,list,show}`."""

from __future__ import annotations

import asyncio
from typing import Annotated

import structlog
import typer

from flyer_generator.brand_kit.scraper import fetch_brand_kit
from flyer_generator.brand_kit.storage import (
    list_brand_kits,
    load_brand_kit,
)
from flyer_generator.errors import BrandKitError

app = typer.Typer(
    help="Brand-kit scraper and applier (Phase 18).",
    no_args_is_help=True,
)
logger = structlog.get_logger()


@app.command()
def fetch(
    url: Annotated[str, typer.Argument(help="Website URL to scrape.")],
    slug: Annotated[
        str,
        typer.Option(
            "--slug",
            help="Output slug (folder name under .brand-kits/).",
        ),
    ],
    force: Annotated[
        bool,
        typer.Option("--force", help="Overwrite an existing kit with the same slug."),
    ] = False,
) -> None:
    """Scrape `url` into `.brand-kits/<slug>/`."""
    try:
        kit = asyncio.run(fetch_brand_kit(url, slug, force=force))
    except BrandKitError as err:
        typer.echo(f"Error: {err}", err=True)
        for k, v in (err.context or {}).items():
            typer.echo(f"  {k}: {v}", err=True)
        raise typer.Exit(2) from err
```

**Deviation:** Phase 19 ships five commands: `post`, `campaign`, `list-platforms`, `list-intents`, `show-rules`. The `post`/`campaign` commands each take ~10 flags (see 19-CONTEXT.md §CLI surface), so use separate helper functions rather than fat `@app.command()` bodies. `typer.Exit(2)` on any `SocialError`.

---

### `flyer_generator/social/__init__.py` (package barrel export)

**Analog:** `flyer_generator/brand_kit/__init__.py`
**Why:** Phase 18's Plan 07 style — consolidated re-exports with `__all__ = sorted([...])` so IDE autocomplete and `from flyer_generator.social import Post, Campaign` both work.

**Pattern to mirror** (lines 24-98):
```python
from __future__ import annotations

from flyer_generator.brand_kit.applier import apply_brand_kit
from flyer_generator.brand_kit.audit import (
    AuditIssue,
    AuditReport,
    audit_render,
    iterate_audit_loop,
    remediate_contrast,
    remediate_density,
)
from flyer_generator.brand_kit.contrast import (
    ContrastPair,
    ContrastReport,
    classify_level,
    ensure_aa,
    passes_aa,
    passes_aaa,
    remediate,
    wcag_ratio,
)
from flyer_generator.brand_kit.models import (
    BrandKit,
    BrandLogo,
    BrandPalette,
    BrandPhotoHints,
    BrandTypography,
    BrandVoice,
    ColorUsage,
)
# ...

__all__ = sorted(
    [
        "BrandKit",
        "BrandLogo",
        # ...
    ]
)
```

**Deviation:** Re-export Post, Campaign, PostBrief, PostSpec, PlatformRules, ValidationReport, ValidationIssue, Platform, Intent, SocialAuditReport, generate_post, generate_campaign, audit_post, load_post_template, list_post_templates, resolve_campaign_dir, save_post, load_post, list_campaigns, plus per-platform `validate_post` re-exports. Follow the category-comment pattern (`# Data models`, `# Audit`, `# Storage`).

---

### `flyer_generator/social/audit.py` (platform-aware post audit)

**Analog:** `flyer_generator/brand_kit/audit.py`
**Why:** CONTEXT.md §Audit strategy explicitly says "Extend `brand_kit.audit_render` → new `flyer_generator/social/audit.py::audit_post`". The AuditIssue/AuditReport pattern (severity/category/detail + `is_clean` property) transfers verbatim; platform_compliance/link_policy/readability are new categories layered on top.

**Pattern to mirror** (lines 77-107, AuditIssue/AuditReport shape):
```python
class AuditIssue(BaseModel):
    """A single issue raised by ``audit_render``."""

    model_config = ConfigDict(extra="forbid")

    severity: Literal["info", "warn", "error"]
    category: Literal["whitespace", "contrast", "density"]
    panel: str | None = None
    content_key: str | None = None
    detail: str
    suggested_remediation: str | None = None


class AuditReport(BaseModel):
    """Aggregate verdict: whitespace density per panel, contrast pairs, content-key fill, issues."""

    model_config = ConfigDict(extra="forbid")

    whitespace: dict[str, float] = Field(default_factory=dict)
    contrast: ContrastReport = Field(default_factory=ContrastReport)
    density: dict[str, float] = Field(default_factory=dict)
    issues: list[AuditIssue] = Field(default_factory=list)
    cycle: int = 0

    @property
    def is_clean(self) -> bool:
        """No FAIL contrast, no WARN/ERROR issues (info is fine)."""
        if not self.contrast.overall_aa_pass:
            return False
        return not any(i.severity in ("warn", "error") for i in self.issues)
```

**PNG-safety pattern** (lines 270-285, mandatory for any new Pillow code):
```python
try:
    img = Image.open(io.BytesIO(rendered_png_bytes)).convert("RGB")
except Exception as err:  # noqa: BLE001 -- untrusted PNG bytes
    raise BrandKitAuditError(
        "could not open rendered PNG",
        cycles=cycle,
        error=str(err),
    ) from err
sheet_w, sheet_h = img.size
if sheet_w * sheet_h > _MAX_IMAGE_MP:
    raise BrandKitAuditError(...)
```

**Deviation:** Phase 19 extends category enum to `Literal["whitespace", "contrast", "density", "platform_compliance", "link_policy", "readability"]`. `SocialAuditReport` wraps (does not subclass) `AuditReport` to keep the Phase 18 class pure — add fields `validation: ValidationReport`, `readability_grade: float`, `hashtag_issues: list[ValidationIssue]`. The `is_clean` property must also check `validation.passed`. Use `tobytes()` (never `getdata()`) per line 161 convention.

---

### `flyer_generator/social/renderer.py` (SVG -> PNG + Pillow crop)

**Analog:** `flyer_generator/brochure/schema_renderer/renderer.py::render_schema_brochure` (primary, for SVG composition) + Pillow ImageOps.fit usage in research
**Why:** Phase 19's renderer is a thin wrapper — it reuses the schema-renderer rasterization primitives and adds per-platform crop. The `model_copy(update={...})` pattern for immutable template mutation (accent_override style) is directly reusable when applying brand-kit palette.

**Pattern to mirror** (lines 752-759, immutable template mutation):
```python
if accent_override is not None:
    template = template.model_copy(
        update={
            "palette": template.palette.model_copy(
                update={"accent_default": accent_override}
            )
        }
    )
```

**Pillow crop pattern** (from 19-RESEARCH.md §Pillow API, recommended):
```python
from PIL import Image, ImageOps

def crop_hero_for_platform(source: Image.Image, target_w: int, target_h: int) -> Image.Image:
    return ImageOps.fit(
        source,
        size=(target_w, target_h),
        method=Image.Resampling.LANCZOS,
        centering=(0.5, 0.5),
    )
```

**Deviation:** Social posts have a single panel (not six), so no `_render_sheet` per-panel loop. Call the existing `render_schema_brochure` once with a 1-panel template OR factor out the per-panel SVG emitter. Prefer the **thin-wrapper** path: build a one-panel PostTemplate, call the schema renderer, rasterize via CairoSVG, apply the Pillow crop. `PLATFORM_CROP_SIZES` lives module-scope in this file (see 19-RESEARCH.md §Aspect math).

---

### `flyer_generator/social/voice.py` (BrandVoice-aware prompt assembly)

**Analog:** `flyer_generator/brochure/schema_renderer/text_gen.py::_render_budget_prompt` + `_format_brief`
**Why:** Phase 19 needs the same "compose a structured system+user prompt from typed inputs" pattern that `_format_brief` already demonstrates — pull fields off a Pydantic model, emit as bullet lines, return a list[str] that the caller joins.

**Pattern to mirror** (text_gen.py lines 254-290):
```python
def _format_brief(brief: BrochureBrief) -> list[str]:
    """Serialize a BrochureBrief into a compact bullet block for the LLM."""
    out: list[str] = ["", "INTAKE BRIEF (ground truth — use verbatim where possible):"]
    if brief.value_proposition:
        out.append(f"- Value proposition: {brief.value_proposition}")
    if brief.target_audience:
        out.append(f"- Target audience: {brief.target_audience}")
    if brief.brand_voice:
        out.append(f"- Brand voice: {brief.brand_voice}")
    if brief.offerings:
        out.append(f"- Offerings: {', '.join(brief.offerings)}")
    # ...
    return out
```

**System-prompt prepend pattern** (19-RESEARCH.md §BrandVoice Integration §System prompt injection):
```
VOICE DIRECTIVE (copy must sound like this brand):
  Tone: {brand_voice.tone}
  Exemplar phrases (match cadence, do not quote verbatim):
    - "{phrase_1}"
    - "{phrase_2}"
  Banned words / phrases (NEVER use these — find a synonym):
    - "{word_1}"
    - "{word_2}"

[... existing system prompt continues ...]
```

**Deviation:** This file is the new home of `format_voice_directive(brand_voice: BrandVoice | None) -> str` (returns "" when None) and `generate_social_copy(brief, brand_voice, platform_rules) -> dict[str, str]`. Also owns the banned-word regex compiler:
```python
import re
def _enforce_banned_words(text: str, banned: list[str]) -> list[str]:
    if not banned:
        return []
    pattern = re.compile(
        r"\b(" + "|".join(re.escape(w) for w in banned) + r")\b",
        re.IGNORECASE,
    )
    return pattern.findall(text)
```

---

### `flyer_generator/social/generator.py` (single-post orchestrator)

**Analog:** `flyer_generator/brochure/schema_renderer/text_gen.py::generate_content_from_prompt` (for the orchestrator shape — optional client, async with `_owns_client` close) + `flyer_generator/brand_kit/scraper.py::fetch_brand_kit` (for trace_id bind + Settings-driven I/O)
**Why:** The generator is a composition of (load template, build voice-aware prompt, call text_gen, render SVG, rasterize, audit, validate) — each step already exists; the orchestrator just sequences them.

**Pattern to mirror** (text_gen.py lines 555-647, the orchestrator skeleton):
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
) -> BrochureContent:
    if settings is None:
        settings = Settings()
    _owns_client = False
    if text_client is None:
        text_client = build_text_client(settings)
        _owns_client = True
    try:
        # ... orchestration ...
        return _normalize_to_brochure_content(data, template, brief=brief, supplied_contact=contact)
    finally:
        if _owns_client and hasattr(text_client, "aclose"):
            await text_client.aclose()
```

**Trace-id binding pattern** (brand_kit/audit.py line 609-610):
```python
trace_id = uuid.uuid4().hex
log = logger.bind(trace_id=trace_id, audit_side=side, max_cycles=max_cycles)
log.info("audit_loop_start")
```

**Deviation:** Signature is `async def generate_post(brief: PostBrief, brand_kit: BrandKit, *, template: PostTemplate | None = None, settings: Settings | None = None, text_client=None, comfy_client=None, audit: bool = True) -> Post`. Reuse `flyer_generator.brochure.schema_renderer.image_gate.generate_template_images` (do NOT rewrite ComfyCloud). Hand off to `social/audit.py::audit_post` and `social/platforms/<platform>.validate`. Text-only branch: if `template.image_slot is None`, skip image_gate entirely (19-RESEARCH.md §Open Risks #8).

---

### `flyer_generator/social/campaign.py` (fan-out orchestrator with shared hero)

**Analog:** `flyer_generator/brochure/schema_renderer/image_gate.py::generate_template_images` (for `asyncio.gather`-based fan-out) + `flyer_generator/brand_kit/audit.py::iterate_audit_loop` (for the structured-log trace_id pattern)
**Why:** Campaign mode is the cost-optimization layer (one hero, N crops, N per-platform copy calls). Shape parallels `iterate_audit_loop`'s orchestration style.

**Pattern to mirror** (image_gate.py async fan-out style — consult full file, approximate shape):
```python
async def generate_template_images(
    template: TemplateSchema,
    content: BrochureContent,
    *,
    settings: Settings,
    comfy_client: ComfyClient | None = None,
) -> dict[str, bytes]:
    # ... collect slots, build tasks, asyncio.gather with return_exceptions=True
    # ... failed slots omitted; logged with structlog
```

**Deviation:** `generate_campaign(brief, brand_kit, platforms, *, settings, text_client, comfy_client) -> Campaign`. Step 1: pick workflow per 19-RESEARCH.md §"What the planner must decide" (`turbo_portrait` if IG story requested, else `standard_square`); generate ONE hero at native dims; Pillow-upscale to 2048² via LANCZOS. Step 2: for each platform, `asyncio.gather(generate_post_with_preloaded_hero(p, brief, kit, source_hero) for p in platforms)`. Step 3: write `campaign.json` + `source_hero.png` + per-platform dirs. Bind `trace_id` once at entry; pass `log = logger.bind(trace_id=..., campaign_id=..., n_platforms=...)` through. ULID generation:
```python
from ulid import ULID
campaign_id = str(ULID())
```

---

### `flyer_generator/social/platforms/linkedin.py` (rules + validator)

**Analog:** `flyer_generator/brand_kit/contrast.py` (module-scope frozen data + pure-function validator)
**Why:** Platform rules are pure data (PlatformRules constant at module scope, frozen model) + pure function (`validate(post, rules) -> ValidationReport`). This is the same shape contrast.py uses for WCAG thresholds + `wcag_ratio`/`passes_aa`.

**Pattern to mirror** (from 19-RESEARCH.md §Validation Contract, the recommended shape for all four platforms):
```python
from flyer_generator.social.models import Platform, Post, PlatformRules, ValidationIssue, ValidationReport
from flyer_generator.social.validation import (
    check_char_limit,
    check_hashtag_count,
    check_image_bytes,
    check_image_aspect,
)

RULES = PlatformRules(
    platform="linkedin",
    body_max_chars=3000,
    body_recommended_max=2500,
    body_visible_before_truncation=210,
    hashtag_hard_max=30,
    hashtag_recommended_max=4,
    image_aspects=(
        ImageAspect(width=1200, height=627, aspect_ratio=1.91, role="link_preview"),
        ImageAspect(width=1200, height=1200, aspect_ratio=1.0, role="feed_square"),
    ),
    image_max_bytes=5 * 1024 * 1024,
    image_recommended_max_bytes=1 * 1024 * 1024,
    images_per_post_max=1,
    clickable_links_in_body=True,
    strips_links_in_caption=False,
)


def validate(post: Post, rules: PlatformRules = RULES) -> ValidationReport:
    issues: list[ValidationIssue] = []
    if issue := check_char_limit(post.copy.body, rules.body_max_chars, "copy.body", "LINKEDIN_BODY_OVER"):
        issues.append(issue)
    issues.extend(check_hashtag_count(post.copy.hashtags, rules.hashtag_hard_max, "copy.hashtags"))
    if post.image_bytes is not None:
        issues.extend(check_image_bytes(len(post.image_bytes), rules.image_max_bytes, rules.image_recommended_max_bytes))
        w, h = _pillow_dims(post.image_bytes)
        issues.extend(check_image_aspect(w, h, rules.image_aspects))
    return ValidationReport(platform=rules.platform, issues=issues)
```

**Rule-id namespace** (stable strings, per 19-RESEARCH.md):
- LinkedIn: `LINKEDIN_BODY_OVER`, `LINKEDIN_HASHTAG_COUNT_OVER`, `LINKEDIN_IMAGE_BYTES_OVER`, `LINKEDIN_IMAGE_ASPECT_MISMATCH`
- Twitter: `TWITTER_TEXT_OVER`, `TWITTER_IMAGE_COUNT_OVER`
- Instagram: `INSTAGRAM_CAPTION_OVER`, `INSTAGRAM_HASHTAG_COUNT_OVER`, `INSTAGRAM_LINK_IN_CAPTION`, `INSTAGRAM_IMAGE_BYTES_OVER`
- Facebook: `FACEBOOK_BODY_LONG` (warn-only — no hard cap)

**Deviation:** Each of the four `platforms/{name}.py` files follows this template verbatim. `instagram.py` adds a unique call to `check_no_urls_in_text(post.copy.body, "INSTAGRAM_LINK_IN_CAPTION")`. `twitter.py` adds `check_image_count(post.images, rules.images_per_post_max)`. All four register into `platforms/__init__.py::PLATFORM_REGISTRY: dict[Platform, tuple[PlatformRules, ValidateFn]]`.

---

### `flyer_generator/social/schemas/schema_model.py` (PostTemplate Pydantic)

**Analog:** `flyer_generator/brochure/schema_renderer/schema_model.py`
**Why:** Direct shape reuse — the fill/stroke/gradient Pydantic union types, the Literal-based role/kind taxonomies, and `ConfigDict(extra="forbid")` all apply to post templates.

**Pattern to mirror** (schema_model.py lines 11-60, Literal-based taxonomy + Fill discriminator):
```python
from __future__ import annotations

from typing import Annotated, Literal, Union

from pydantic import BaseModel, ConfigDict, Field, field_validator

from flyer_generator.brochure.models import validate_hex_color

_TextRole = Literal[
    "cover_title",
    "cover_subtitle",
    "section_heading",
    "body",
    # ...
    "static",
]
```

**Deviation:** 19-RESEARCH.md §Template Schema Design gives the target shape. Reuse (don't duplicate) `ShapeElement`, `SolidFill`, `LinearGradientFill`, `Canvas`, `LogoPlaceholder` from `brochure/schema_renderer/schema_model.py`. New types: `ImageSlot` (bbox + aspect + slot_name), `TextSlot` (bbox + role + content_key + max_chars + color_role + font_role + align/valign), `PostTemplate` (schema_version + name + platform + intent + canvas + optional palette/typography + text_budgets + image_slot + shapes + text_slots + logo_slot). TextSlot.role is a narrower Literal union than brochure's: `Literal["title","body","cta","caption_overlay","hashtag_strip","org_mark"]`.

---

### `flyer_generator/social/schemas/loader.py` (JSON loader)

**Analog:** `flyer_generator/brochure/schema_renderer/loader.py`
**Why:** Copy this file almost verbatim — name/path lookup + JSON -> Pydantic validation.

**Pattern to mirror** (lines 1-39, entire file):
```python
"""Template schema loader — reads JSON, validates via Pydantic."""

from __future__ import annotations

import json
from pathlib import Path

from flyer_generator.brochure.schema_renderer.schema_model import TemplateSchema

_SCHEMAS_DIR = Path(__file__).parent.parent / "schemas"


def load_template(name_or_path: str) -> TemplateSchema:
    if name_or_path.endswith(".json"):
        path = Path(name_or_path)
    else:
        path = _SCHEMAS_DIR / f"{name_or_path}.json"

    if not path.exists():
        available = list_templates()
        raise FileNotFoundError(
            f"Schema template not found: {path}. Available: {available}"
        )

    raw = json.loads(path.read_text(encoding="utf-8"))
    return TemplateSchema.model_validate(raw)


def list_templates() -> list[str]:
    if not _SCHEMAS_DIR.exists():
        return []
    return sorted(p.stem for p in _SCHEMAS_DIR.glob("*.json"))
```

**Deviation:** `_SCHEMAS_DIR = Path(__file__).parent` (schemas live alongside loader.py, not in a sibling dir). Function renames: `load_post_template`, `list_post_templates`. Template name convention: `<platform>__<intent>.json` (double underscore — parse-back helper recommended: `def parse_template_name(name: str) -> tuple[Platform, Intent]`).

---

### `flyer_generator/social/schemas/*.json` (template data, 12+ files)

**Analog:** `flyer_generator/brochure/schemas/editorial_classic.json`
**Why:** Same JSON authoring conventions — `schema_version: "1"`, hex-color discipline, bbox coords, layered `z` ordering, role-named text elements.

**Pattern to mirror** (editorial_classic.json lines 1-38, the top-level skeleton + one panel):
```json
{
  "schema_version": "1",
  "name": "editorial_classic",
  "description": "Serif typography, thin accent rules, one hero image placeholder...",
  "tone_keywords": ["professional", "authoritative", "corporate", "editorial"],
  "canvas": { "width": 1100, "height": 2550 },
  "palette": {
    "accent_default": "#1E3A5F",
    "neutral_dark": "#1A1A1A",
    "neutral_light": "#FAFAF7",
    "muted": "#E8E6E1"
  },
  "typography": {
    "heading_family": "'Playfair Display', 'Times New Roman', serif",
    "body_family": "'Source Serif Pro', Georgia, serif",
    ...
  },
  "panels": {
    "front_cover": {
      "description": "Hero image top half, title+subtitle mid, category label top, org bottom.",
      "background": { "type": "solid", "color": "#FAFAF7" },
      "elements": [
        { "type": "shape", "kind": "rect", "rect": [0, 0, 1100, 8], "fill": { "type": "solid", "color": "#1E3A5F" }, "bleed": "top", "z": 0 },
        { "type": "image_placeholder", "bbox": [0, 120, 1100, 1420], "slot": "hero", ... },
        { "type": "text", "bbox": [80, 1650, 940, 540], "role": "cover_title", "content_key": "title", ... }
      ]
    }
  }
}
```

**Deviation:** Per 19-RESEARCH.md §Template Schema Design, post schemas replace `panels` with a single flat structure: `canvas`, `text_budgets`, `image_slot`, `shapes`, `text_slots`, `logo_slot`. Palette is **nullable** (None means "inherit from applied brand kit"); typography is **nullable** (same). Canvas dims match platform aspect: 1200×627 (LI link preview), 1200×1200 (LI/FB square), 1200×675 (Twitter), 1080×1080 (IG/FB square), 1080×1350 (IG/FB portrait), 1080×1920 (IG story), 1200×630 (FB link preview). Ship at least 12 files: `{linkedin,twitter,instagram,facebook}__{announcement,value-prop,testimonial}.json`.

---

### `flyer_generator/brochure/schema_renderer/text_gen.py` (MODIFY — BrandVoice wiring)

**Analog:** existing `generate_content_from_prompt` at this same file (extend in place, don't fork)
**Why:** Plan 01. The signature additions are backwards-compatible; the `_SYSTEM_PROMPT` gets a prepended voice-directive block that collapses to "(none)" when `brand_voice=None`.

**Existing signature to extend** (text_gen.py lines 555-565):
```python
async def generate_content_from_prompt(
    template: TemplateSchema,
    prompt: str,
    *,
    audience: str | None = None,
    color_accent: str = "#1E3A5F",
    brief: BrochureBrief | None = None,
    contact=None,  # ContactBlock | None
    settings: Settings | None = None,
    text_client: TextClient | None = None,
) -> BrochureContent:
```

**Add these two params (default None, backwards-compatible)**:
```python
    brand_voice: BrandVoice | None = None,          # NEW
    tighter_budgets: dict[str, int] | None = None,  # NEW — unblocks density remediation
```

**Existing retry-on-overflow pattern to mimic** (lines 622-641, the shape of the voice-violation retry):
```python
if overflow and _MAX_RETRIES > 0:
    logger.info("text_gen_overflow_retry", keys=overflow)
    retry_user = (
        user_prompt
        + "\n\nYour previous response overflowed on these fields: "
        + ", ".join(overflow)
        + ". Rewrite each in ~20% fewer characters and return the full JSON again."
    )
    try:
        raw2 = await text_client.complete(
            system=_SYSTEM_PROMPT,
            user=retry_user,
            response_format="json",
        )
        data = json.loads(raw2)
        data, _ = _apply_budgets(data, budgets, bullets_per_key)
    except (VisionAPIError, VisionResponseParseError, json.JSONDecodeError) as err:
        logger.warning("text_gen_retry_failed", error=str(err))
```

**Deviation:** Add a parallel `if banned_matches and _voice_retries > 0:` branch that issues one retry with "Your previous response used banned words: {matches}. Rewrite without them." After one retry if violations persist, raise `BrandVoiceViolationError(message, banned_matches=[...], keys=[...])`. Log `text_gen_banned_word_violation`. The voice directive block is prepended to `_SYSTEM_PROMPT` via a new `_assemble_system_prompt(brand_voice: BrandVoice | None) -> str` helper — do NOT mutate the module-level constant.

---

### `flyer_generator/errors.py` (MODIFY — add SocialError tree + BrandVoiceViolationError)

**Analog:** existing `BrandKitError` tree at lines 123-148
**Why:** New exception classes follow the same `FlyerGeneratorError` base + one-liner docstring + optional `__init__` override for typed context fields (cycles, remaining_issues).

**Pattern to mirror** (errors.py lines 123-148):
```python
class BrandKitError(FlyerGeneratorError):
    """Base for all brand-kit errors."""


class BrandKitScrapeError(BrandKitError):
    """Scraper exhausted both Playwright and BS4 paths without usable data."""


class BrandKitContrastError(BrandKitError):
    """Contrast remediation exhausted options with no passing swap."""


class BrandKitAuditError(BrandKitError):
    """Audit loop hit max cycles without clean pass (only raised in strict mode)."""

    def __init__(
        self,
        message: str,
        *,
        cycles: int = 0,
        remaining_issues: list[object] | None = None,
        **kwargs: object,
    ) -> None:
        super().__init__(message, **kwargs)
        self.cycles = cycles
        self.remaining_issues = remaining_issues or []
```

**Classes to add** (per 19-CONTEXT.md §Error hierarchy):
```python
class SocialError(FlyerGeneratorError):
    """Base for all social-posting errors."""


class PostValidationError(SocialError):
    """Hard platform-validation failure (e.g. body over hard cap)."""

    def __init__(
        self,
        message: str,
        *,
        platform: str | None = None,
        issues: list[object] | None = None,
        **kwargs: object,
    ) -> None:
        super().__init__(message, **kwargs)
        self.platform = platform
        self.issues = issues or []


class PlatformUnsupportedError(SocialError):
    """Unknown platform string passed to generator/campaign."""


class IntentUnsupportedError(SocialError):
    """Unknown intent string."""


class CampaignError(SocialError):
    """Campaign-level orchestration failure."""


class BrandVoiceViolationError(BrandKitError):
    """LLM copy contained banned-word or voice violation after retries exhausted."""

    def __init__(
        self,
        message: str,
        *,
        banned_matches: list[str] | None = None,
        keys: list[str] | None = None,
        **kwargs: object,
    ) -> None:
        super().__init__(message, **kwargs)
        self.banned_matches = banned_matches or []
        self.keys = keys or []
```

**Deviation:** `BrandVoiceViolationError` **extends BrandKitError** (not SocialError) because Phase 18 is the wiring site (text_gen lives under brochure) and this is a brand-kit voice violation that surfaces anywhere `BrandVoice` is wired. `PostValidationError` carries `platform` + `issues` for structured CLI output.

---

### `flyer_generator/config.py` (MODIFY — add social_campaigns_dir)

**Analog:** existing `brand_kits_dir` field at line 77
**Why:** Mirror the Pydantic-Settings + env-var + default-Path field pattern verbatim.

**Pattern to mirror** (config.py line 76-78):
```python
# Brand kit storage (Phase 18). Configurable via FLYER_BRAND_KITS_DIR env var.
brand_kits_dir: Path = Path(".brand-kits")
```

**Add:**
```python
# Social campaigns storage (Phase 19). Configurable via FLYER_SOCIAL_CAMPAIGNS_DIR env var.
social_campaigns_dir: Path = Path(".social-campaigns")
```

---

### `.social-template.json` (new, tracked at repo root)

**Analog:** `.brand-kit-template.json` at repo root
**Why:** Same role — human-readable reference schema for users authoring Campaign or Post by hand, tracked in git so IDE schema-detection works.

**Pattern to mirror** (`.brand-kit-template.json` top-level structure — a pretty-printed valid instance of the top-level model with realistic example values).

**Deviation:** Populate with a plausible Campaign: topic, platforms (list), one PostBrief per platform, realistic CTAs. Include inline comments via a sibling `.md` section in README is NOT how the brand-kit version does it — keep it pure JSON, let the field names and example values document themselves. Validate shape via `tests/social/test_models.py::test_template_roundtrip` (mirror `tests/brand_kit/test_models.py::TEMPLATE_FILE` pattern at lines 29-30).

---

### `.gitignore` (MODIFY — add .social-campaigns/)

**Analog:** existing `.brand-kits/` line in .gitignore
**Why:** Same role — untracked local artifact output.

**Add one line** (alphabetically, near `.brand-kits/`):
```
.social-campaigns/
```

---

### `pyproject.toml` (MODIFY — add python-ulid)

**Analog:** existing dependency entries
**Why:** Add `python-ulid>=3.1.0` per 19-RESEARCH.md §Storage ID Format (verified on PyPI, v3.1.0 April 2026, lexicographic sortability, 26-char Base32).

**Deviation:** Add to `[project.dependencies]` not `[project.optional-dependencies.dev]` — ULID is used in shipping code (`social/campaign.py`), not just tests.

---

### Tests under `tests/social/`

**Analogs (test-by-test mapping):**

**`tests/social/test_models.py`** -> `tests/brand_kit/test_models.py`
```python
# Pattern to mirror (lines 1-45, the file-header + fixture-builder shape)
"""Test PostSpec, Post, Campaign, PostBrief, PlatformRules, ValidationReport: round-trip, partial, validation."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest
from pydantic import ValidationError

from flyer_generator.social.models import (
    Campaign,
    Intent,
    Platform,
    Post,
    PostBrief,
    PostSpec,
    PlatformRules,
    ValidationIssue,
    ValidationReport,
)


REPO_ROOT = Path(__file__).resolve().parents[2]
TEMPLATE_FILE = REPO_ROOT / ".social-template.json"


def _minimal_brief() -> PostBrief:
    return PostBrief(
        topic="test",
        intent="value-prop",
        platform="linkedin",
    )
```

**`tests/social/test_storage.py`** -> `tests/brand_kit/test_storage.py` (lines 1-80) — identical shape; adapt slug checks to also cover campaign_id.

**`tests/social/test_cli.py`** -> `tests/brand_kit/test_cli.py` — invoke `typer.testing.CliRunner` against the five commands.

**`tests/social/test_audit.py`** -> `tests/brand_kit/test_audit.py` — covers `audit_post` including new categories.

**`tests/social/test_platforms_linkedin.py`** (+ twitter, instagram, facebook) -> `tests/brand_kit/test_contrast.py` — each file is a table of (input, expected_issues) tuples exercising the pass case + every fail case per 19-RESEARCH.md §Testing Matrix.

**`tests/social/test_voice.py`** (BrandVoice wiring in text_gen) -> `tests/brand_kit/test_applier.py` — uses `pytest-asyncio` + `respx` to mock `text_client.complete` and assert:
- system prompt contains voice directive when brand_voice passed
- system prompt does NOT contain directive when brand_voice=None (backwards compat)
- banned-word violation triggers one retry
- after retry failure, raises `BrandVoiceViolationError`
- case-insensitive word-boundary matching

**`tests/social/test_integration.py`** -> `tests/brand_kit/test_integration.py` — end-to-end `generate_post(thunderstaff, linkedin, value-prop)` with mocked LLM + Comfy, real CairoSVG rasterize.

**`tests/social/test_package_exports.py`** -> `tests/brand_kit/test_package_exports.py` — asserts every name in `__all__` is importable and the list is `sorted`.

**Deviation:** All tests use **direct-module imports** (`from flyer_generator.social.models import Post` not `from flyer_generator.social import Post`) until the wave that owns `__init__.py` lands, to avoid same-wave `__init__.py` write conflicts (the same B1 rule Phase 18 used — see `tests/brand_kit/test_models.py` docstring lines 4-7). Mark gallery-style real-service tests with `@pytest.mark.slow` and deselect by default (mirror Phase 18 convention per 19-RESEARCH.md §Testing Matrix).

---

## Shared Patterns

### Logger binding (all orchestrators)

**Source:** `flyer_generator/brand_kit/audit.py` lines 609-611
**Apply to:** `social/generator.py`, `social/campaign.py`, `social/__main__.py`
```python
import uuid
import structlog

logger = structlog.get_logger()

trace_id = uuid.uuid4().hex
log = logger.bind(trace_id=trace_id, post_platform=..., intent=...)
log.info("generate_post_start")
```

### Pydantic v2 frozen data with `ConfigDict(extra="forbid")`

**Source:** `flyer_generator/brand_kit/models.py` line 27
**Apply to:** Every new Pydantic model in `social/models.py` and `social/schemas/schema_model.py`
```python
model_config = ConfigDict(extra="forbid")
# For registry singletons (PlatformRules, ImageAspect):
model_config = ConfigDict(extra="forbid", frozen=True)
```

### Immutable model transform

**Source:** `flyer_generator/brochure/schema_renderer/renderer.py` lines 752-759 + `flyer_generator/brand_kit/applier.py` lines 227-229
**Apply to:** `social/renderer.py` (applying brand_kit to PostTemplate), `social/audit.py::remediate_*` (if added)
```python
new_template = template.model_copy(
    update={"palette": new_palette, "typography": new_typography}
)
```

### Lazy import to break module-load cycles

**Source:** `flyer_generator/brand_kit/storage.py` lines 23-24, 131-132
**Apply to:** `social/storage.py` (for `Post`, `Campaign` inside TYPE_CHECKING), anywhere a same-wave model-storage cycle is possible.
```python
from typing import TYPE_CHECKING
if TYPE_CHECKING:  # pragma: no cover
    from flyer_generator.social.models import Post, Campaign

# Inside function body when actual use is needed:
from flyer_generator.social.models import Post  # noqa: PLC0415
```

### Pillow: `tobytes()` not `getdata()`

**Source:** `flyer_generator/brand_kit/audit.py` line 161 + comment
**Apply to:** Any Pillow pixel access in `social/audit.py`, `social/renderer.py`
```python
# Pillow 14 deprecates ``getdata``; ``tobytes()`` is the forward-compatible
# accessor and yields raw R,G,B,R,G,B,... bytes for an RGB-mode image.
raw = img.tobytes()
```

### PNG safety cap (50 MP)

**Source:** `flyer_generator/brand_kit/audit.py` lines 115-117, 270-285
**Apply to:** `social/audit.py::audit_post`, `social/renderer.py` if rasterizing untrusted input
```python
_MAX_IMAGE_MP = 50_000_000

try:
    img = Image.open(io.BytesIO(rendered_png_bytes)).convert("RGB")
except Exception as err:
    raise SocialError("could not open rendered PNG", error=str(err)) from err
w, h = img.size
if w * h > _MAX_IMAGE_MP:
    raise SocialError("rendered PNG exceeds 50 MP cap", width=w, height=h)
```

### LLM retry + model-fallback

**Source:** `flyer_generator/stages/llm_retry.py::_call_with_retry` (already wired to `text_client`)
**Apply to:** `social/voice.py::generate_social_copy` — **do not build a new retry loop**. Go through `build_text_client(settings)` and the existing `text_client.complete()` call (which is already wrapped by `_call_with_retry` in `brochure/llm_client.py`).

### CLI error handling

**Source:** `flyer_generator/brand_kit/__main__.py` lines 42-47
**Apply to:** `social/__main__.py` every command
```python
try:
    result = asyncio.run(orchestrator(...))
except SocialError as err:
    typer.echo(f"Error: {err}", err=True)
    for k, v in (err.context or {}).items():
        typer.echo(f"  {k}: {v}", err=True)
    raise typer.Exit(2) from err
```

### Path-traversal + containment

**Source:** `flyer_generator/brand_kit/storage.py` lines 49-75, also `flyer_generator/brand_kit/applier.py` lines 182-192 (logo path resolve + containment)
**Apply to:** `social/storage.py` (campaign dir resolution), `social/renderer.py` if loading template from user-supplied path
```python
candidate = (kit_dir / primary.path).resolve()
try:
    candidate.relative_to(kit_dir)
except ValueError:
    logger.warning("path_traversal_blocked", path=primary.path)
    return None
```

### Test `__init__.py` quarantine (direct-module imports only)

**Source:** `tests/brand_kit/test_models.py` lines 4-7, `tests/brand_kit/test_storage.py` lines 2-7
**Apply to:** ALL `tests/social/*.py` files during waves before `social/__init__.py` lands
```python
"""Per checker B1: imports use direct-module paths so this plan
never writes to the package-root __init__.py (which is a docstring-
only stub until the final wave)."""

# Good:
from flyer_generator.social.models import Post

# Disallowed until __init__.py wave:
# from flyer_generator.social import Post
```

### ULID generation

**Source:** new dep `python-ulid>=3.1.0` (no existing analog in repo)
**Apply to:** `social/campaign.py`, `social/__main__.py` (when `--campaign-id` is omitted)
```python
from ulid import ULID
campaign_id = str(ULID())  # 26-char Base32, lexicographically sortable
```

### Pillow crop (campaign hero fan-out)

**Source:** new pattern per 19-RESEARCH.md §Campaign Image Crop Strategy (no existing analog — Phase 18 did not crop)
**Apply to:** `social/renderer.py`, `social/campaign.py`
```python
from PIL import Image, ImageOps

def crop_hero_for_platform(source: Image.Image, target_w: int, target_h: int) -> Image.Image:
    return ImageOps.fit(
        source,
        size=(target_w, target_h),
        method=Image.Resampling.LANCZOS,
        centering=(0.5, 0.5),
    )
```

---

## No Analog Found

All Phase 19 files have a Phase 18 or schema_renderer analog — **zero files require fresh-greenfield patterns**. Two exceptions are noted above because they import new libraries (not "no analog", just "new library usage"):

| File | New library | Reason |
|---|---|---|
| `flyer_generator/social/campaign.py` | `python-ulid` | No existing ULID consumer in repo (new dep per 19-RESEARCH.md §Storage ID Format). Planner must verify `python-ulid>=3.1.0` is added to `pyproject.toml` in the same plan. |
| `flyer_generator/social/renderer.py` / `campaign.py` | `PIL.ImageOps.fit` | Pillow is already a dep (brand_kit/audit.py uses `Image.open`, `resize`, `tobytes`); `ImageOps.fit` is a Pillow submodule function not yet used in repo. No version bump needed (Pillow>=12 includes it). |

---

## Metadata

**Analog search scope:**
- `flyer_generator/brand_kit/*` (8 files — primary pattern source per CONTEXT §canonical_refs)
- `flyer_generator/brochure/schema_renderer/*` (8 files — rendering pipeline reuse)
- `flyer_generator/brochure/schemas/*.json` (13 template JSON files — post schema authoring convention)
- `flyer_generator/stages/llm_retry.py` (shared retry wrapper)
- `flyer_generator/errors.py` (error hierarchy extension point)
- `flyer_generator/config.py` (Settings extension point)
- `tests/brand_kit/*` (13 files — test pattern templates)

**Files scanned:** ~50

**Pattern extraction date:** 2026-04-21

**Primary pattern sources (by frequency of reference):**
1. `flyer_generator/brand_kit/models.py` — Pydantic model shape
2. `flyer_generator/brand_kit/storage.py` — filesystem I/O + containment
3. `flyer_generator/brand_kit/audit.py` — AuditReport/AuditIssue + PNG safety + iterate loop
4. `flyer_generator/brand_kit/__main__.py` — typer CLI shape
5. `flyer_generator/brand_kit/__init__.py` — consolidated re-exports with sorted `__all__`
6. `flyer_generator/brochure/schema_renderer/text_gen.py` — LLM orchestrator + Plan 01 modification site
7. `flyer_generator/brochure/schema_renderer/schema_model.py` — template Pydantic
8. `flyer_generator/brochure/schema_renderer/loader.py` — template JSON loader
9. `flyer_generator/brochure/schema_renderer/image_gate.py` — ComfyCloud orchestration reuse surface
10. `flyer_generator/brochure/schemas/editorial_classic.json` — template JSON authoring style

## PATTERN MAPPING COMPLETE
