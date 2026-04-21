---
phase: 19-social-media-posting-system
plan: 01
subsystem: brand-kit

tags: [brand-voice, text-gen, tdd, llm, regex, error-hierarchy]

# Dependency graph
requires:
  - phase: 18-brand-kit
    provides: BrandVoice pydantic model (tone, example_phrases, banned_words)
  - phase: 17
    provides: brochure.schema_renderer.text_gen.generate_content_from_prompt entry point
provides:
  - "generate_content_from_prompt(brand_voice: BrandVoice | None = None) — backwards-compatible voice kwarg"
  - "generate_content_from_prompt(tighter_budgets: dict[str, int] | None = None) — forward-compat stub for Plan 19-08"
  - "_assemble_system_prompt helper that prepends a VOICE DIRECTIVE block to the LLM system prompt"
  - "_enforce_banned_words helper: case-insensitive, word-boundary, regex-injection-safe (re.escape)"
  - "_scan_banned helper: recursive (key_path, match) walker over nested JSON"
  - "BrandVoiceViolationError(BrandKitError) with banned_matches + keys context fields"
  - "Voice retry branch: one stricter retry before BrandVoiceViolationError; runs before overflow retry to avoid composition"
  - "Structured log event text_gen_banned_word_violation (audit trail — threat T-19-01-05)"
affects: [19-06-social-copy, 19-07-social-copy-variants, 19-09-cross-channel-copy]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "BrandVoice → system-prompt prepend via pure-function helper; module-level prompt constant never mutated"
    - "Banned-word scan uses re.escape on every token to neutralize regex injection from user-supplied brand kits"
    - "Voice retry runs BEFORE overflow retry to keep retry branches composable"
    - "Typed domain error (BrandVoiceViolationError) carries banned_matches + keys so callers can surface the violation without re-parsing the message"

key-files:
  created:
    - tests/social/__init__.py
    - tests/social/test_voice.py
  modified:
    - flyer_generator/errors.py
    - flyer_generator/brochure/schema_renderer/text_gen.py

key-decisions:
  - "BrandVoiceViolationError extends BrandKitError (not SocialError) because the wiring site lives in brochure/ and this is a brand-kit violation that surfaces anywhere BrandVoice is used."
  - "Voice retry runs BEFORE the existing overflow retry so voice and budget retries never compound or collide (19-RESEARCH.md Open Risk #4)."
  - "re.escape every banned-word token before regex compile — prevents regex-injection from a crafted brand.json (threat T-19-01-01)."
  - "tighter_budgets accepted now (as an explicit `_ = tighter_budgets` no-op) to give Plan 19-08 a stable signature without forcing another signature churn."
  - "_assemble_system_prompt returns a new string rather than mutating _SYSTEM_PROMPT so the module constant stays immutable and tests can rely on its stable identity."

patterns-established:
  - "Helpers like _enforce_banned_words and _scan_banned live at module scope (not nested) so tests can import and unit-test them directly."
  - "Banned-word matching: `re.compile(r'\\b(' + '|'.join(re.escape(w) for w in banned) + r')\\b', re.IGNORECASE)` — case-insensitive + word-boundary + injection-safe."

requirements-completed: [SOC-04]

# Metrics
duration: ~20 min
completed: 2026-04-21
---

# Phase 19 Plan 01: BrandVoice Wiring Summary

**BrandVoice (tone, example_phrases, banned_words) now reaches the LLM via an additive `brand_voice` kwarg on `generate_content_from_prompt`, with case-insensitive regex-injection-safe banned-word scan + exactly-one retry + typed `BrandVoiceViolationError` on second violation.**

## Performance

- **Duration:** ~20 min (TDD x2 cycles)
- **Started:** 2026-04-21T19:00Z (approx)
- **Completed:** 2026-04-21T19:20Z
- **Tasks:** 2 completed (each executed RED → GREEN)
- **Files modified:** 4 (2 created, 2 modified)

## Accomplishments

- `BrandVoiceViolationError(BrandKitError)` added to the error hierarchy with `banned_matches` + `keys` context fields and empty-list defaults.
- `generate_content_from_prompt` now accepts `brand_voice: BrandVoice | None = None` (backwards-compatible — existing callers unaffected, all 734 brochure + brand_kit tests still green).
- `_assemble_system_prompt` prepends a `VOICE DIRECTIVE` block (tone + exemplar phrases + banned words) to the system prompt when `brand_voice` is supplied; returns base unchanged when `None`.
- `_enforce_banned_words` + `_scan_banned` provide regex-injection-safe banned-word detection with word-boundary + case-insensitive semantics.
- Voice retry loop: one stricter retry with the banned words echoed into the user prompt, then `BrandVoiceViolationError` raised with `banned_matches + keys` populated.
- Structured log event `text_gen_banned_word_violation` records the audit trail (keys + matches).
- 11 tests in `tests/social/test_voice.py` all pass (3 Task 1 + 8 Task 2 — Task 2 added 8 rather than the 6 minimum required by the plan for tighter leaf-level coverage).
- Full non-slow test suite: 932 passed, 0 failed.

## Task Commits

Each task followed RED → GREEN TDD:

1. **Task 1 (RED):** `7632302` — `test(19-01): add failing tests for BrandVoiceViolationError`
2. **Task 1 (GREEN):** `7c3df20` — `feat(19-01): add BrandVoiceViolationError to error hierarchy`
3. **Task 2 (RED):** `c18ea2f` — `test(19-01): add failing tests for voice wiring into text_gen`
4. **Task 2 (GREEN):** `26dbd59` — `feat(19-01): wire BrandVoice into generate_content_from_prompt`

_Plan metadata (SUMMARY.md) will be committed by the final-commit step below._

## Files Created/Modified

- `tests/social/__init__.py` (created) — package marker so pytest collects `tests/social/`
- `tests/social/test_voice.py` (created) — 11 tests covering error class, helpers, integration
- `flyer_generator/errors.py` (modified) — added `BrandVoiceViolationError` after `BrandKitAuditError`
- `flyer_generator/brochure/schema_renderer/text_gen.py` (modified):
  - new imports (`re`, `BrandVoice`, `BrandVoiceViolationError`)
  - new module-level helpers `_enforce_banned_words`, `_assemble_system_prompt`, `_scan_banned`
  - `generate_content_from_prompt` signature extended with `brand_voice` + `tighter_budgets`
  - system-prompt derivation swapped from raw `_SYSTEM_PROMPT` to `_assemble_system_prompt(brand_voice, _SYSTEM_PROMPT)`
  - voice-retry branch inserted before the existing overflow-retry branch

## Decisions Made

- BrandVoiceViolationError extends BrandKitError (not SocialError) — keeps the error class near the data type it validates.
- Voice retry precedes overflow retry so retry branches never compose (eliminates Open Risk #4 from 19-RESEARCH.md).
- `re.escape` applied to every banned-word token on every compile (threat T-19-01-01 mitigation).
- `tighter_budgets` accepted now as a no-op to lock in the signature Plan 19-08 expects; explicit `_ = tighter_budgets` avoids lint warnings without changing runtime behavior.
- `_assemble_system_prompt` returns a new string rather than mutating `_SYSTEM_PROMPT` (immutable-constant discipline).
- Unlike the plan-spec default of `tone: str | None = None`, the real `BrandVoice.tone` field is `str` (required); `(brand_voice.tone or "").strip() or "(none)"` handles both the plan's contract and the actual model without needing a models.py change.

## Deviations from Plan

### 1. [Rule 2 — Missing critical handling] Voice retry tolerates JSON parse error on the retry response

- **Found during:** Task 2 implementation
- **Issue:** The plan's voice-retry code block did not wrap `json.loads(raw2)` in a try/except. A mocked or real LLM returning non-JSON on the retry would raise `json.JSONDecodeError` and mask the violation — the user would see a parse error instead of `BrandVoiceViolationError`.
- **Fix:** Wrapped the retry `complete(...)` + `json.loads(...)` in `try/except (VisionResponseParseError, json.JSONDecodeError)` with `logger.warning("text_gen_voice_retry_parse_failed", ...)`. If the retry fails to parse, we keep the original `data` and the subsequent `_scan_banned(data, banned_words)` still triggers the raise — so the violation path is preserved.
- **Files modified:** `flyer_generator/brochure/schema_renderer/text_gen.py`
- **Commit:** `26dbd59`

### 2. [Rule 2 — Missing critical handling] Explicit consumption of `tighter_budgets` to satisfy strict-lint

- **Found during:** Task 2 implementation
- **Issue:** The plan introduced `tighter_budgets` as "accepted but unused this plan" without telling the reader/linter it was intentional. Leaving the kwarg untouched risks a future ruff rule flagging it.
- **Fix:** Added `_ = tighter_budgets` with a one-line comment noting the Plan 19-08 handoff. No behavior change.
- **Files modified:** `flyer_generator/brochure/schema_renderer/text_gen.py`
- **Commit:** `26dbd59`

### 3. [Rule 2 — Missing critical handling] Added 2 extra tests beyond the plan's 6 voice-wiring tests

- **Found during:** Task 2 test authoring
- **Issue:** The plan specified 6 voice-related tests; leaf-level coverage of the system-prompt-backwards-compat property and the retry-raise-key-path property were missing.
- **Fix:** Added `test_system_prompt_omits_voice_directive_when_brand_voice_none` and a specific assertion inside `test_voice_raises_after_retry_still_banned` that the raised `keys` list includes a `body_paragraphs` path (not just any path). Total voice-wiring tests: 8 (plan minimum: 6).
- **Files modified:** `tests/social/test_voice.py`
- **Commit:** `c18ea2f`

---

**Total deviations:** 3 auto-fixed (all Rule 2: missing-critical-handling hardening).
**Impact on plan:** No scope creep. Each deviation preserves the plan's contract and closes a small-but-real correctness hole. All plan acceptance grep-criteria still pass.

## Issues Encountered

None. TDD RED/GREEN cycles proceeded cleanly on the first GREEN attempt for both tasks. Full non-slow test suite (932 tests) green.

## Threat Flags

Plan-scoped threat register covers all new surface — no new flags.

## User Setup Required

None — this is a pure internal refactor. No env vars, no external services, no new dependencies.

## Next Phase Readiness

- Plan 19-06 / 19-07 / 19-09 (social copy generation variants) can now call `generate_content_from_prompt(..., brand_voice=...)` directly; no further plumbing required.
- Phase 18 deferred item D-SOC-01 (BrandVoice wiring) is resolved.
- `tighter_budgets` is now a stable kwarg so Plan 19-08 can wire per-platform budgets without another signature churn.

## Self-Check: PASSED

- `flyer_generator/errors.py`: `class BrandVoiceViolationError(BrandKitError):` at line 151 — FOUND
- `flyer_generator/brochure/schema_renderer/text_gen.py`: `def _assemble_system_prompt` at line 577, `def _enforce_banned_words` at line 561, `brand_voice: BrandVoice | None = None` at line 643, `tighter_budgets: dict[str, int] | None = None` at line 644, `VOICE DIRECTIVE` at line 596, `raise BrandVoiceViolationError` at line 750, `text_gen_banned_word_violation` at line 725 — all FOUND
- `tests/social/__init__.py`: FOUND
- `tests/social/test_voice.py`: FOUND, 11 tests pass
- Commits FOUND: `7632302`, `7c3df20`, `c18ea2f`, `26dbd59`
- Regression guard: `pytest tests/brochure/ tests/brand_kit/ -x -q` → 734 passed; `pytest tests/ -x -q -m "not slow"` → 932 passed, 2 deselected.

---
*Phase: 19-social-media-posting-system*
*Plan: 01*
*Completed: 2026-04-21*
