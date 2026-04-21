---
phase: 19-social-media-posting-system
plan: 09
subsystem: social
tags: [campaign, cli, barrel, shared-hero, typer, SOC-01, SOC-06, SOC-08, SOC-10, SOC-11]
requirements:
  - SOC-01
  - SOC-06
  - SOC-08
  - SOC-10
  - SOC-11
dependency_graph:
  requires:
    - 19-01 (voice directive + BrandVoiceViolationError)
    - 19-02 (Campaign/Post/PostBrief/PostSpec + storage + ULID dep)
    - 19-03 (PLATFORM_REGISTRY + load_platform_rules + validate_post + readability)
    - 19-04 (crop.PLATFORM_CROP_SIZES + crop_hero_for_platform + upscale_source_hero + workflow_map.select_workflow_for_campaign)
    - 19-05 (schemas.loader + schemas.schema_model)
    - 19-06 (renderer.render_post)
    - 19-07 (generator.generate_post + image_gate.generate_single_image helper)
    - 19-08 (audit.audit_post + SocialAuditReport)
    - 18 (brand_kit.storage.load_brand_kit)
  provides:
    - flyer_generator.social (barrel export with sorted __all__, 33 public names)
    - flyer_generator.social.campaign.generate_campaign
    - flyer_generator.social.campaign._generate_shared_hero
    - flyer_generator.social.__main__ (typer CLI: post, campaign, list-platforms, list-intents, show-rules)
  affects:
    - flyer_generator/social/__init__.py (replaced Plan 02 scaffold with full barrel)
tech_stack:
  added: []
  patterns:
    - "Shared-hero fan-out: ONE ComfyCloud call -> upscale 2048x2048 -> N per-platform crops -> N per-platform copy generations (independent banned-word/hashtag/char-budget enforcement per platform)"
    - "asyncio.gather with return_exceptions=True for per-platform independence: one platform failure doesn't sink the whole campaign"
    - "_PreloadedHero shim injects the cropped hero back through generate_post's comfy_client slot so per-platform render reuses the same pipeline without a second ComfyCloud call"
    - "CLI shape mirrors flyer_generator.brand_kit.__main__: typer.Typer(no_args_is_help=True), Annotated parameters, SocialError/BrandKitError -> echo-stderr-then-exit(2), asyncio.run() wrapper for async orchestrators"
    - "Barrel __init__.py imports every public symbol + sorted(__all__) literal list (matches brand_kit/__init__.py Plan 18-07 pattern)"
key_files:
  created:
    - flyer_generator/social/campaign.py
    - flyer_generator/social/__main__.py
    - tests/social/test_campaign.py
    - tests/social/test_cli.py
    - tests/social/test_package_exports.py
    - tests/social/test_integration.py
  modified:
    - flyer_generator/social/__init__.py
decisions:
  - "str(ULID()) for campaign_id + trace_id (W-05 guard: .hex is not on the ulid.ULID class in python-ulid>=3.1.0)"
  - "Hero generation routes through generate_single_image helper (image_gate) rather than direct ComfyClient construction (W-01 guard: matches Plan 07 B-05 fix)"
  - "Per-platform copy regeneration is deliberate: each platform has distinct char budgets, hashtag caps, banned-word retry state, and strips_links_in_caption policy that a single truncated shared copy cannot honor"
  - "Campaign.posts values are serialized dicts (post.model_dump(exclude={'image_bytes'})) with __has_image flag; image bytes stay in-memory for downstream CLI persistence — matches Plan 02's Campaign.posts: dict[str, object] shape"
  - "Instagram cropping uses feed_square (1080x1080) by default; include_story=True switches to 9:16 story (1080x1920) + forces portrait workflow across the whole campaign"
  - "CLI post command persists via save_post(slug=brand_kit, campaign_id=cid, template_name='{platform}__{intent}', base_dir=output); cid defaults to fresh ULID unless --campaign-id override given"
  - "show-rules emits JSON (platform.rules.model_dump) rather than a bespoke human string — JSON is grep-friendly AND human-readable at the same time"
  - "Docstring rewording: dropped literal 'ComfyClient(settings=settings)', 'client.submit(workflow=', 'ULID().hex', and banned-SDK module names from docstrings so repo-wide grep-based regression guards return 0 matches (semantic content preserved via paraphrase)"
metrics:
  duration_minutes: 18
  tasks_completed: 3
  files_created: 6
  files_modified: 1
  tests_added: 13
  tests_passing: 1136
  completed_date: 2026-04-21
---

# Phase 19 Plan 09: Campaign Orchestrator + CLI + Barrel Summary

Ship the public API surface of Phase 19: the campaign orchestrator that shares ONE generated hero across N platforms, the five-command typer CLI (`post`, `campaign`, `list-platforms`, `list-intents`, `show-rules`), the consolidated `flyer_generator.social` barrel export, and two end-to-end integration tests. After this plan, `pip install .` lets a user run `python -m flyer_generator.social post --brand-kit thunderstaff --platform linkedin --intent value-prop --topic "..." --output /tmp/out` end-to-end (mocked-LLM + mocked-Comfy in CI, real services in production).

## What Shipped

### Task 1 — `flyer_generator/social/campaign.py`

`generate_campaign(brand_kit, topic, platforms, intent, *, include_story, cta, image_hint, settings, text_client, comfy_client, audit) -> Campaign` — 275-line async orchestrator.

Pipeline:
1. Select a single workflow name via `select_workflow_for_campaign(platforms, include_story=...)`.
2. Generate ONE source hero via `_generate_shared_hero(...)` — either from an injected `comfy_client.generate_image(...)` mock OR via the shared `generate_single_image` helper in `flyer_generator.brochure.schema_renderer.image_gate`. Upscales native output to 2048x2048 via Pillow LANCZOS.
3. Fan out per-platform via `asyncio.gather(return_exceptions=True)`:
   - Build a `PostBrief`, load the `{platform}__{intent}` template.
   - Crop the shared hero to the platform's primary `PLATFORM_CROP_SIZES` role (link_preview for LI/FB, primary for TW, feed_square or story for IG).
   - Inject the cropped hero through a tiny `_PreloadedHero` shim so `generate_post` reuses its full copy-gen → render → validate → audit pipeline without a second ComfyCloud call.
4. Serialize each `Post` via `model_dump(exclude={'image_bytes'})`, tag with `__has_image` flag, assemble into `Campaign(campaign_id=str(ULID()), brand_kit_slug=..., posts=...)`.

Structured logging via `structlog` — `trace_id` + `campaign_id` bound on every log line (T-19-09-07 mitigation).

Tests (`tests/social/test_campaign.py`, 3 tests):
- Shared-hero invariant: 3 platforms → `comfy.calls == 1`, `text.calls >= 3`, `len(campaign.posts) == 3`.
- Empty platforms → `CampaignError`.
- `include_story=True` drives portrait workflow; `campaign.campaign_id` is a 26-char ULID.

### Task 2 — Barrel + CLI

**`flyer_generator/social/__init__.py`** (replaces Plan 02 scaffold): imports every public symbol from 10 submodules, exposes 33 names via `__all__ = sorted([...])`. Satisfies SOC-01.

**`flyer_generator/social/__main__.py`**: typer CLI with 5 commands:
| Command | Purpose |
|---------|---------|
| `post` | Generate one post, persist to `<output>/<brand_kit>/<campaign_id>/<template_name>/post.json`+`image.png` |
| `campaign` | Multi-platform campaign, persist to `<output>/<slug>/<campaign_id>/campaign.json` |
| `list-platforms` | Echo 4 supported platforms (sorted) |
| `list-intents` | Echo 3 supported intents |
| `show-rules <platform>` | JSON-dump `PlatformRules.model_dump()` |

Error handling: `SocialError` + `BrandKitError` + `FileNotFoundError` (for missing brand kit) all echo the message to stderr and exit with code 2. Mirrors `flyer_generator.brand_kit.__main__` shape exactly.

Tests:
- `tests/social/test_cli.py` (4 tests): list-platforms prints all 4 platforms, list-intents prints all 3 intents, `show-rules linkedin` emits valid JSON with `platform: "linkedin"` + `body_max_chars: 3000`, `show-rules myspace` exits 2.
- `tests/social/test_package_exports.py` (4 tests): `_EXPECTED_EXPORTS` set (33 names) ⊆ `__all__`, `__all__ == sorted(__all__)`, every `__all__` entry is importable, and the **SOC-11 guard** — a filesystem walk of `flyer_generator/social/**/*.py` that rejects any `import <mod>` or `from <mod>` matching 8 banned publishing SDKs: `linkedin_api`, `tweepy`, `facebook_sdk`, `facebook_business`, `google_api_python_client`, `googleapiclient`, `instagrapi`, `instagram_private_api`.

### Task 3 — End-to-End Integration Tests

`tests/social/test_integration.py` (2 tests, both completing in < 3s):
1. `test_generate_post_linkedin_value_prop_end_to_end_mocked`: full pipeline (PostBrief → load template → LLM copy (canned JSON) → hero (canned 1024x1024 PNG) → render PNG → validate → audit). Asserts: platform+intent match, copy.title matches, 4 hashtags, rendered image is 1200x627 (LinkedIn link_preview), validation passed, audit ran.
2. `test_generate_campaign_three_platforms_shares_hero_and_regenerates_copy`: campaign across `linkedin`, `twitter`, `instagram`. Asserts: exactly 1 ComfyCloud call (hero shared), >=3 LLM text calls (copy per platform), 3 posts keyed by `{platform}__value-prop`.

## Phase 19 Coverage Map

Final plan of 9. Full Phase 19 requirement coverage:

| Requirement | Summary | Satisfied By |
|---|---|---|
| SOC-01 | Consolidated `flyer_generator.social` public API | Plan 19-09 (this plan, barrel __init__.py) |
| SOC-02 | Platform rules registry | Plan 19-03 |
| SOC-03 | Per-platform validators | Plan 19-03 |
| SOC-04 | Post template schemas + 12 built-in templates | Plan 19-05 |
| SOC-05 | Brand-kit-aware renderer | Plan 19-06 |
| SOC-06 | Campaign shared-hero orchestrator | Plan 19-09 (this plan, campaign.py) |
| SOC-07 | Platform-aware post audit | Plan 19-08 |
| SOC-08 | 5-command typer CLI | Plan 19-09 (this plan, __main__.py) |
| SOC-09 | Single-post orchestrator | Plan 19-07 |
| SOC-10 | Full Phase 19 test suite <5 min | Plan 19-09 (this plan, integration tests + phase gate) |
| SOC-11 | No publishing-SDK imports in social package | Plan 19-09 (this plan, banned-import guard test) |

## Phase 19 File Inventory

New modules shipped by Phase 19 (by plan):

| Plan | Files |
|------|-------|
| 19-01 | flyer_generator/social/voice.py (format_voice_directive, generate_social_copy) |
| 19-02 | flyer_generator/social/models.py (Campaign, Post, PostBrief, PostSpec, PlatformRules, ValidationReport, etc.); flyer_generator/social/storage.py (save/load_post + save/load_campaign + resolve_campaign_dir); flyer_generator/social/platforms/__init__.py (PLATFORM_REGISTRY scaffold); flyer_generator/errors.py (SocialError, PostValidationError, PlatformUnsupportedError, IntentUnsupportedError, CampaignError); pyproject.toml (python-ulid>=3.1.0) |
| 19-03 | flyer_generator/social/platforms/{linkedin,twitter,instagram,facebook}.py; flyer_generator/social/validation.py (shared validators); flyer_generator/social/readability.py (flesch_kincaid_grade) |
| 19-04 | flyer_generator/social/crop.py (PLATFORM_CROP_SIZES, crop_hero_for_platform, upscale_source_hero, crop_all_platforms); flyer_generator/social/workflow_map.py (select_workflow_for_aspect, select_workflow_for_campaign, PLATFORM_TO_ASPECT) |
| 19-05 | flyer_generator/social/schemas/schema_model.py (PostTemplate, ImageSlot, TextSlot); flyer_generator/social/schemas/loader.py; 12 schema JSON files (4 platforms × 3 intents) |
| 19-06 | flyer_generator/social/renderer.py (render_post, _apply_brand_kit_to_post_template) |
| 19-07 | flyer_generator/social/generator.py (generate_post); flyer_generator/brochure/schema_renderer/image_gate.py (extracted shared generate_single_image helper) |
| 19-08 | flyer_generator/social/audit.py (SocialAuditReport, audit_post); flyer_generator/brand_kit/audit.py (shared scan_text_contrast + scan_image_density primitives extracted) |
| 19-09 | flyer_generator/social/campaign.py (generate_campaign); flyer_generator/social/__init__.py (barrel); flyer_generator/social/__main__.py (typer CLI) |

Test suite across all 9 plans: ~206 social tests, all non-slow, <7s total.

## Deviations from Plan

### Rule 3 — Auto-fix blocking issues

**1. `python-ulid` not installed in venv**
- **Found during:** Task 1 (first tool run `.venv/bin/python -c "from ulid import ULID; ..."` failed with `ModuleNotFoundError`).
- **Issue:** `pyproject.toml` pinned `python-ulid>=3.1.0` (Plan 02) but `.venv` at `/home/hoyack/work/autocreative/.venv` predated that pin and never got `uv sync`ed to pick it up.
- **Fix:** `.venv/bin/python -m pip install "python-ulid>=3.1.0"`.
- **Files modified:** none (dev-environment only, no source change).
- **Commit:** n/a (ran inline before Task 1 commit).

### Rule 1 — Auto-fixed bugs (preemptive guards)

**2. Docstring text inside the social package was triggering repo-wide regression-guard greps**
- **Found during:** Task 1 acceptance-criteria verification.
- **Issue:** The plan's `<action>` block included docstrings that literally named the banned patterns — `ComfyClient(settings=settings)`, `client.submit(workflow=`, and `ULID().hex` — as a "DO NOT do this" warning for future maintainers. But the top-level success criteria use plain `grep -rn "...pattern..."` checks that don't distinguish between docstring mentions and actual call sites. Same thing happened in `__init__.py` where the SOC-11 guard ("no `linkedin_api`, `tweepy` …") used the banned module names verbatim.
- **Fix:** Rewrote the three docstrings to paraphrase the warning semantically without the literal patterns. In `campaign.py`: "single-arg ComfyClient init (missing http_client)" and "submit with workflow= + prompt= keyword args" and "`.hex` attribute is NOT on the `ulid.ULID` class". In `__init__.py`: "No publishing-SDK client libraries are imported anywhere …; the banned-import guard test … enforces that invariant at CI time."
- **Files modified:** `flyer_generator/social/campaign.py`, `flyer_generator/social/__init__.py`.
- **Commit:** 1ff175f (campaign.py docstring), c036569 (__init__.py docstring).

**3. Duplicated `CampaignError` wrap on hero-generation failure**
- **Found during:** Task 1 implementation walkthrough.
- **Issue:** `_generate_shared_hero` wraps `ComfySubmitError` in `CampaignError`. The outer `generate_campaign` then catches bare `Exception` and wraps *that* in another `CampaignError(f"hero generation failed: {err}")`, producing double-wrapped errors like `CampaignError("hero generation failed: CampaignError('shared hero generation failed: ...')")`.
- **Fix:** Added an explicit `except CampaignError: ... raise` clause before the bare-Exception handler so pre-wrapped errors re-raise as-is.
- **Files modified:** `flyer_generator/social/campaign.py`.
- **Commit:** 1ff175f.

### Deviation: CLI `post` output path

The plan's `<behavior>` specified `/tmp/out/<campaign_id>/linkedin__value-prop/post.json`. `save_post`'s actual signature is `save_post(post, slug, campaign_id, template_name, *, base_dir)` which writes `<base_dir>/<slug>/<campaign_id>/<template_name>/...` — the slug layer is mandatory (it's part of the path-containment guard in `resolve_campaign_dir`). CLI now passes `base_dir=output`, `slug=brand_kit`, so the final path is `<output>/<brand_kit_slug>/<campaign_id>/<template_name>/post.json`. Consistent with the `campaign` command's `save_campaign(camp, base_dir=output)` which also anchors under `<output>/<brand_kit_slug>/<campaign_id>/`.

## Authentication Gates

None. All external services (ComfyCloud + Ollama/Anthropic) are injected via `comfy_client` + `text_client` params and mocked in every CI test. Production CLI usage still requires `FLYER_COMFYCLOUD_API_KEY` + an LLM endpoint, but those are config-time concerns inherited from Phase 01/02 and not gates for this plan's execution.

## Known Stubs

None. Every file ships production-ready; no `TODO`/`FIXME`/placeholder data flows anywhere in the three new modules.

## Known Limitations (for Phase 20)

Phase 19 is intentionally scoped to **artifact production only**. Deferred to Phase 20 (publishing):

- **No real platform posting**: SOC-11 is enforced by the banned-import guard test. A future Phase 20 would add `flyer_generator.publishing.{linkedin,twitter,instagram,facebook}` modules (in a NEW top-level package, not under `social/`) with OAuth flows, rate-limit handling, and dry-run modes.
- **No scheduling / queueing**: `generate_campaign` produces artifacts synchronously; there is no persisted job queue, no cron hook, no Celery/RQ integration. Artifacts land on disk and the user does whatever they want with them.
- **No analytics / tracking**: Campaign.posts has no `published_at`, `post_url`, `impressions`, etc. fields. Those belong to the publishing layer.
- **No mixed-intent campaigns**: `generate_campaign` takes a single `intent` applied to every platform. A `linkedin=value-prop` + `twitter=announcement` campaign would need a new `CampaignSpec` input model — out of scope for v1.
- **Source-hero upscale at 2048×2048 is via Pillow LANCZOS only**. 19-RESEARCH.md §Open Risks #2 flagged potential artifacts at 2x; mitigation deferred to Phase 20+ (SDXL refiner or Topaz pass would be candidates).
- **Quota enforcement deferred**: T-19-09-06 — a user could submit `--platforms linkedin,twitter,instagram,facebook --include-story` and burn 1 hero + 8 LLM calls. Accepted for v1; quota belongs to a later plan that adds generation budgets.

## Verification Snapshot

```
$ python -m pytest tests/social/ -x -q -m "not slow"
206 passed, 1 warning in 6.85s

$ python -m pytest tests/ -x -q -m "not slow"
1136 passed, 2 deselected, 1 warning in 78.33s (0:01:18)

$ python -c "from flyer_generator.social import Post, PostSpec, Platform, generate_post, generate_campaign, load_platform_rules, validate_post"
(exits 0)

$ python -m flyer_generator.social list-platforms
facebook
instagram
linkedin
twitter

$ python -m flyer_generator.social list-intents
announcement
value-prop
testimonial

$ python -m flyer_generator.social show-rules linkedin | head -3
{
  "platform": "linkedin",
  "body_max_chars": 3000,

$ grep -rn "ULID().hex" flyer_generator/social/
(no matches)

$ grep -rn "ComfyClient(settings=settings)" flyer_generator/
(no matches)

$ grep -rnE "linkedin_api|tweepy|facebook_sdk|facebook_business|googleapiclient|google_api_python_client|instagrapi|instagram_private_api" flyer_generator/social/
(no matches)
```

## Commits

| Task | Commit | Message |
|------|--------|---------|
| 1 | `1ff175f` | feat(19-09): campaign.py shared-hero orchestrator with per-platform fan-out |
| 2 | `c036569` | feat(19-09): social package barrel + 5-command typer CLI |
| 3 | `827e9cc` | test(19-09): end-to-end integration tests with mocked LLM + Comfy |

## Self-Check: PASSED

- `flyer_generator/social/campaign.py`: FOUND
- `flyer_generator/social/__main__.py`: FOUND
- `flyer_generator/social/__init__.py`: FOUND (modified)
- `tests/social/test_campaign.py`: FOUND
- `tests/social/test_cli.py`: FOUND
- `tests/social/test_package_exports.py`: FOUND
- `tests/social/test_integration.py`: FOUND
- Commit `1ff175f`: FOUND in `git log`
- Commit `c036569`: FOUND in `git log`
- Commit `827e9cc`: FOUND in `git log`
