---
phase: 19-social-media-posting-system
plan: 03
subsystem: social
tags: [social, validation, platforms, rules, readability]
requirements: [SOC-02]
dependency_graph:
  requires:
    - flyer_generator.social.models (Plan 19-02: Post, PostCopy, PlatformRules, ImageAspect, ValidationIssue, ValidationReport)
    - flyer_generator.errors (SocialError, PlatformUnsupportedError)
    - PIL.Image (Pillow 12.2.0 — decode PNG/JPEG untrusted bytes with 50 MP cap)
  provides:
    - flyer_generator.social.validation (check_char_limit, check_hashtag_count, check_image_bytes, check_image_aspect, check_image_count, check_no_urls_in_text, _pillow_dims, validate_post)
    - flyer_generator.social.readability (flesch_kincaid_grade, _count_syllables)
    - flyer_generator.social.platforms.linkedin (RULES, validate)
    - flyer_generator.social.platforms.twitter (RULES, validate)
    - flyer_generator.social.platforms.x (RULES, validate — re-export of twitter)
    - flyer_generator.social.platforms.instagram (RULES, validate)
    - flyer_generator.social.platforms.facebook (RULES, validate)
    - flyer_generator.social.platforms (PLATFORM_REGISTRY, load_platform_rules, validate_post)
  affects:
    - Plan 19-05 renderer (will use PlatformRules.body_max_chars / hashtag_recommended_max / image_aspects to budget text and choose template)
    - Plan 19-07 orchestrator (will call validate_post to gate generated posts)
    - Plan 19-08 audit (will consume flesch_kincaid_grade to map readability_grade_max -> ValidationIssue)
tech-stack:
  added:
    - none (pure-Python; uses existing Pillow + stdlib re/io/typing)
  patterns:
    - module-scope RULES constant + pure-function validate(post, rules) (mirrors brand_kit/contrast.py passes_aa / wcag_ratio shape — 19-PATTERNS.md line 28)
    - shared check_* primitives with caller-supplied rule_id so the same primitive (e.g. check_char_limit) emits LINKEDIN_BODY_OVER for LinkedIn and TWITTER_TEXT_OVER for Twitter
    - Instagram re-maps HASHTAG_COUNT_CAP -> INSTAGRAM_HASHTAG_COUNT_OVER via ValidationIssue.model_copy(update=) to keep the primitive platform-agnostic
    - _pillow_dims as single decoding site for untrusted bytes, enforcing 50 MP cap (same as brand_kit/audit.py)
    - twitter.validate carries image_count kwarg (default 1) so callers staging multi-image tweets can exercise TWITTER_IMAGE_COUNT_OVER without inventing a new shape in the Post model
    - platforms/x.py as pure re-export alias (the 2024+ rebrand) so `from flyer_generator.social.platforms import x as x_mod; x_mod.RULES is twitter.RULES`
    - PLATFORM_REGISTRY dict at module scope is effectively read-only from callers (T-19-03-06 mitigation)
key-files:
  created:
    - flyer_generator/social/readability.py (38 lines — dependency-free Flesch-Kincaid)
    - flyer_generator/social/validation.py (260 lines — 6 check_* primitives + _pillow_dims + validate_post re-export)
    - flyer_generator/social/platforms/__init__.py (51 lines — registry + load/validate helpers)
    - flyer_generator/social/platforms/linkedin.py (71 lines — RULES + validate)
    - flyer_generator/social/platforms/twitter.py (84 lines — RULES + validate with image_count kwarg)
    - flyer_generator/social/platforms/x.py (8 lines — re-export alias)
    - flyer_generator/social/platforms/instagram.py (89 lines — RULES + validate with HASHTAG_COUNT_CAP re-map + URL-in-caption warn)
    - flyer_generator/social/platforms/facebook.py (99 lines — RULES + validate with FACEBOOK_BODY_LONG warn)
    - tests/social/test_readability.py (34 lines, 4 tests)
    - tests/social/test_platforms_linkedin.py (5 tests)
    - tests/social/test_platforms_twitter.py (6 tests — includes x-alias check)
    - tests/social/test_platforms_instagram.py (6 tests)
    - tests/social/test_platforms_facebook.py (8 tests — includes registry + validate_post dispatch)
  modified:
    - none (all new files)
decisions:
  - Platform-agnostic primitives + caller-supplied rule_id (chose this over one dedicated primitive per platform because rule-value table is platform-specific but rule logic is not)
  - Instagram re-maps HASHTAG_COUNT_CAP -> INSTAGRAM_HASHTAG_COUNT_OVER via ValidationIssue.model_copy(update=) rather than forking the primitive (keeps primitive callable from any platform; Instagram is the only platform with a HARD cap, so only it needs the rename)
  - Instagram URL-in-caption is WARN (not error) — explicit per 19-RESEARCH.md Open Risks #1: users legitimately post captions containing URLs even though they are stripped from clickability; making it an error would block useful content
  - Twitter.validate carries image_count kwarg (default 1) — a single Post model carries one image_bytes field but carousels need to exercise images_per_post_max=4; this keeps Post simple while letting tests and the Plan 07 orchestrator feed real counts
  - platforms/x.py is a pure re-export module (8 lines) not a duplicate RULES block — the 2024+ rebrand is a rename, not a fork; keeping one source of truth for RULES prevents drift
  - flyer_generator.social.validation.validate_post is a thin convenience re-export so the plan-level `from flyer_generator.social.validation import validate_post` contract is satisfied alongside the richer `from flyer_generator.social.platforms import validate_post` (same object, two import paths; see Deviations)
metrics:
  duration: 9min
  completed: 2026-04-21
---

# Phase 19 Plan 03: Platform Rules + Validation Primitives + Readability Summary

Four platform validators (LinkedIn/Twitter-X/Instagram/Facebook) built as module-scope `PlatformRules` constants plus stateless `validate(post, rules)` functions composed from six reusable `check_*` primitives in `validation.py`; readability is a dependency-free Flesch-Kincaid heuristic (38 LoC) that Plan 08's audit loop will consume; registry `PLATFORM_REGISTRY` + `validate_post(post)` dispatch is wired and raises `PlatformUnsupportedError` on unknown strings.

## Tasks Completed

| Task | Name                                                           | Commit (RED / GREEN)    | Files |
| ---- | -------------------------------------------------------------- | ----------------------- | ----- |
| 1    | Shared validation primitives + Flesch-Kincaid readability      | `955cffe` / `e31eaba`   | `flyer_generator/social/readability.py`, `flyer_generator/social/validation.py`, `tests/social/test_readability.py` |
| 2    | Four platform rules modules + registry + per-platform tests    | `04ce46e` / `1523d76`   | `flyer_generator/social/platforms/{__init__,linkedin,twitter,x,instagram,facebook}.py`, `tests/social/test_platforms_{linkedin,twitter,instagram,facebook}.py` |

## Platform Rule Values (locked from 19-RESEARCH.md §Platform Rules, verified April 2026)

| Platform  | body_max | body_rec_max | hashtag_hard_max | hashtag_rec | images_max | image_max_MB | strips_links |
| --------- | -------- | ------------ | ---------------- | ----------- | ---------- | ------------ | ------------ |
| LinkedIn  | 3000     | 2500         | 30               | 4           | 1          | 5            | False        |
| Twitter/X | 280      | —            | None             | 2           | 4          | 5            | False        |
| Instagram | 2200     | —            | 30 (hard)        | 8           | 1          | 30           | **True**     |
| Facebook  | 63206    | 500          | None             | 2           | 1          | 30           | False        |

Image aspects (19-RESEARCH.md §Platform Rules):
- LinkedIn: 1200×627 (link_preview), 1200×1200 (feed_square)
- Twitter/X: 1200×675 (primary)
- Instagram: 1080×1080, 1080×1350, 1080×1920
- Facebook: 1200×630, 1080×1080, 1080×1350

## Rule ID Namespace (platform-specific error identifiers)

- LinkedIn: `LINKEDIN_BODY_OVER`, `LINKEDIN_IMAGE_BYTES_OVER`, `LINKEDIN_IMAGE_BYTES_LARGE`, `LINKEDIN_IMAGE_ASPECT_MISMATCH`
- Twitter: `TWITTER_TEXT_OVER`, `TWITTER_IMAGE_COUNT_OVER`, `TWITTER_IMAGE_BYTES_OVER`, `TWITTER_IMAGE_BYTES_LARGE`, `TWITTER_IMAGE_ASPECT_MISMATCH`
- Instagram: `INSTAGRAM_CAPTION_OVER`, `INSTAGRAM_HASHTAG_COUNT_OVER`, `INSTAGRAM_LINK_IN_CAPTION` (warn), `INSTAGRAM_IMAGE_BYTES_OVER`, `INSTAGRAM_IMAGE_BYTES_LARGE`, `INSTAGRAM_IMAGE_ASPECT_MISMATCH`
- Facebook: `FACEBOOK_BODY_OVER`, `FACEBOOK_BODY_LONG` (warn), `FACEBOOK_IMAGE_BYTES_OVER`, `FACEBOOK_IMAGE_BYTES_LARGE`, `FACEBOOK_IMAGE_ASPECT_MISMATCH`
- Shared (hashtag primitive): `HASHTAG_FORMAT`, `HASHTAG_CHARS`, `HASHTAG_LENGTH` (warn), `HASHTAG_COUNT_CAP` (re-mapped by Instagram to `INSTAGRAM_HASHTAG_COUNT_OVER`)

## Verification

- `python -m pytest tests/social/test_platforms_linkedin.py tests/social/test_platforms_twitter.py tests/social/test_platforms_instagram.py tests/social/test_platforms_facebook.py tests/social/test_readability.py -x -q` → **29 passed** (25 platforms + 4 readability)
- `python -m pytest tests/ -x -q -m "not slow"` → **975 passed, 2 deselected** (zero regressions in Plans 01, 02, or any upstream phase)
- `python -c "from flyer_generator.social.platforms import linkedin, twitter, instagram, facebook; from flyer_generator.social.validation import validate_post; from flyer_generator.social.readability import flesch_kincaid_grade"` → exits 0
- Registry: `set(PLATFORM_REGISTRY) == {'linkedin', 'twitter', 'instagram', 'facebook'}` ✓
- `load_platform_rules('myspace')` raises `PlatformUnsupportedError` ✓
- `platforms.x.RULES is platforms.twitter.RULES` ✓ (single source of truth)

## Deviations from Plan

### Auto-added functionality (Rule 2)

**1. [Rule 2 — API Surface] Added `validate_post` re-export in `validation.py`**
- **Found during:** Task 2 acceptance check
- **Issue:** Plan-level `<success_criteria>` requires `from flyer_generator.social.validation import validate_post` to succeed, but the plan's `<artifacts>` and `<action>` place `validate_post` in `platforms/__init__.py` (not `validation.py`). Without a re-export, the stated success criterion would fail.
- **Fix:** Added a 9-line thin wrapper in `flyer_generator/social/validation.py` that lazy-imports `platforms.validate_post` and dispatches. The function in `platforms` remains the canonical implementation; `validation` is just an import alias.
- **Files modified:** `flyer_generator/social/validation.py` (+13 lines including docstring)
- **Commit:** `1523d76` (bundled with Task 2 GREEN since both sites were added together)
- **Risk:** Minimal — no new behavior; the underlying function is reached by the same code path. Lazy import avoids a circular-import risk (`validation.py` is imported by every `platforms/*.py`, so top-level import of `platforms` inside `validation` would be a cycle).

### Artifacts table variance (cosmetic)

The plan's `<frontmatter>.artifacts` lists `platforms/x.py` under `files_modified` but the module didn't exist before this plan — it's new, not modified. No action required; noting for phase-summary accuracy.

## Auth Gates

None — this plan is pure-Python logic with no network, credentials, or CLI invocations.

## Known Stubs

None. Every exported surface is wired end-to-end:
- `PLATFORM_REGISTRY` populated at import time with 4 real `(RULES, validate_fn)` tuples
- Each `validate()` returns a real `ValidationReport` with real `ValidationIssue` objects (not placeholders)
- Readability heuristic produces real floats (tested against simple + complex English prose)
- No `TODO`, `FIXME`, `coming soon`, or `not available` patterns in any created file

## Threat Flags

None. All trust-boundary work matches the plan's `<threat_model>`:

- **T-19-03-01 (DoS via zip-bomb PNG) — mitigated:** `_pillow_dims` enforces `_MAX_IMAGE_MP = 50_000_000` and wraps `Image.verify()` in `try/except Exception` that raises `SocialError` on malformed bytes.
- **T-19-03-02 (DoS via huge-text URL scan) — mitigated:** Platform validators call `check_char_limit` first; a body over 2200/3000 chars is already flagged with an error-severity issue; `_URL_RE` is still O(n) but the n is bounded.
- **T-19-03-06 (registry bypass) — mitigated:** `PLATFORM_REGISTRY` is a module-level `dict` assigned once at import; `validate_post` is the single dispatch site; callers cannot inject a platform without also mutating `PLATFORM_REGISTRY`.
- **T-19-03-04 (info disclosure in messages) — accepted:** `ValidationIssue.message` echoes counts, bytes, and rule_ids only — no secrets, credentials, or file paths.
- **T-19-03-05 (hashtag list scan DoS) — accepted:** `check_hashtag_count` iterates once over a list that `check_hashtag_count` itself caps at 30 (via the hard-cap error issued before any per-tag loop); no amplification.

## TDD Gate Compliance

Both tasks followed RED → GREEN:

- **Task 1 RED:** `955cffe test(19-03): add failing readability tests` — tests fail with `ModuleNotFoundError: flyer_generator.social.readability` (verified).
- **Task 1 GREEN:** `e31eaba feat(19-03): shared validation primitives + Flesch-Kincaid readability` — 4/4 tests pass.
- **Task 2 RED:** `04ce46e test(19-03): add failing platform validator tests` — tests fail with `ModuleNotFoundError: flyer_generator.social.platforms` (verified).
- **Task 2 GREEN:** `1523d76 feat(19-03): four platform rules + registry + validate_post dispatch` — 25/25 tests pass.

No REFACTOR gate needed — both GREEN implementations landed clean on first pass; the only post-GREEN change was the `validate_post` re-export (a Rule-2 additive change, not a refactor).

## Self-Check: PASSED

**Files created (self-check via `test -f`):**
- `flyer_generator/social/readability.py` — FOUND
- `flyer_generator/social/validation.py` — FOUND
- `flyer_generator/social/platforms/__init__.py` — FOUND
- `flyer_generator/social/platforms/linkedin.py` — FOUND
- `flyer_generator/social/platforms/twitter.py` — FOUND
- `flyer_generator/social/platforms/x.py` — FOUND
- `flyer_generator/social/platforms/instagram.py` — FOUND
- `flyer_generator/social/platforms/facebook.py` — FOUND
- `tests/social/test_readability.py` — FOUND
- `tests/social/test_platforms_linkedin.py` — FOUND
- `tests/social/test_platforms_twitter.py` — FOUND
- `tests/social/test_platforms_instagram.py` — FOUND
- `tests/social/test_platforms_facebook.py` — FOUND

**Commits (verified via `git log --oneline`):**
- `955cffe` (Task 1 RED) — FOUND
- `e31eaba` (Task 1 GREEN) — FOUND
- `04ce46e` (Task 2 RED) — FOUND
- `1523d76` (Task 2 GREEN) — FOUND

**Tests:**
- `pytest tests/social/test_platforms_*.py tests/social/test_readability.py -x -q` → 29 passed
- `pytest tests/ -x -q -m "not slow"` → 975 passed, 2 deselected
