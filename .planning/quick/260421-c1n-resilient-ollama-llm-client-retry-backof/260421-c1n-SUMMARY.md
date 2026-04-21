---
quick_id: 260421-c1n
type: execute
mode: quick
completed: 2026-04-21T14:04:16Z
tasks_completed: 3
tests_before: 902
tests_after: 912
tests_added: 10
regressions: 0
commits:
  - 6ab79a9 — feat: LLM error hierarchy + retry/fallback config fields
  - b9e843b — feat: retry helper + wire both Ollama clients + 10 resilience tests
  - 2399991 — docs: CLAUDE.md LLM Resilience section
files_created:
  - flyer_generator/stages/llm_retry.py
  - tests/test_llm_resilience.py
  - .planning/quick/260421-c1n-resilient-ollama-llm-client-retry-backof/260421-c1n-SUMMARY.md
files_modified:
  - flyer_generator/errors.py
  - flyer_generator/config.py
  - flyer_generator/stages/vision.py
  - flyer_generator/brochure/llm_client.py
  - tests/test_vision.py
  - tests/test_errors.py
  - CLAUDE.md
---

# Quick Task 260421-c1n: Resilient Ollama LLM Client Summary

Introduced a shared retry/backoff helper (`flyer_generator/stages/llm_retry.py::_call_with_retry`) with typed LLM error classes, per-error classification, exponential backoff + jitter, Retry-After honoring (seconds and HTTP-date), and automatic fallthrough to a configurable fallback-model chain. Both Ollama call sites (`VisionEvaluator._post_ollama` and `OllamaTextClient._call`) now route through it. A single flaky 503 from `ollama.com` no longer kills a brochure/flyer run — transient failures retry; model-not-found advances to the next model.

## What Was Built

### New error hierarchy (`flyer_generator/errors.py`)
- `LLMAPIError` (base; carries optional `model`, `status_code`)
- `LLMRateLimitError` (429; carries `retry_after_seconds`)
- `LLMServiceUnavailableError` (500/502/503; retryable)
- `LLMTimeoutError` (ReadTimeout/ConnectTimeout/ConnectError/ReadError; retryable)
- `LLMModelUnavailableError` (404 or body "not found / not loaded / unknown model"; fallthrough)
- `VisionAPIError = LLMAPIError` backwards-compat alias at the bottom of the file

### New Settings fields (`flyer_generator/config.py`)
- `ollama_text_model_fallbacks: list[str]` — default `["kimi-k2.6:cloud", "qwen3.6:35b"]`
- `ollama_vision_model_fallbacks: list[str]` — default `["kimi-k2.6:cloud", "qwen3.6:35b"]`
- `llm_retry_max_attempts: int` — default `3`
- `llm_retry_base_delay: float` — default `1.0`
- `llm_retry_max_delay: float` — default `10.0`
- Env vars: `FLYER_LLM_RETRY_MAX_ATTEMPTS`, `FLYER_OLLAMA_TEXT_MODEL_FALLBACKS`, etc. (comma-separated strings auto-parse to `list[str]`).

### Retry helper (`flyer_generator/stages/llm_retry.py`)
- Classification table preserves the legacy message shape `"Ollama API error {status}: {body}"` so existing regex-matching tests still pass.
- Backoff: `min(max_delay, base_delay × 2^(n-1)) + uniform(0, base_delay × 0.5)`.
- Retry-After parser handles both integer seconds and HTTP-date (via `email.utils.parsedate_to_datetime`), clamped to `max_delay`.
- 400/401/403 → raise immediately (no retry, no fallback).
- 404 / model-not-found body → advance chain immediately (no same-model retry).
- 500/502/503/429/timeouts → retry up to `max_attempts`, then advance chain.
- Structured log events: `llm_retry` (per backoff) and `llm_model_fallback` (per chain advance), both bound with `model`, `attempt`, `max_attempts`.

### Client wire-through
- `stages/vision.py::_post_ollama` — payload no longer pre-sets `model`; helper injects per-attempt model from `[ollama_vision_model, *ollama_vision_model_fallbacks]`. Returns the full JSON dict; content extraction happens in the caller.
- `brochure/llm_client.py::OllamaTextClient._call` — same treatment with text model chain.
- `_call_ollama`, `_call_ollama_retry`, `_call_anthropic*`, `AnthropicTextClient._call` — **unchanged** (Anthropic SDK has its own retry; only the Ollama HTTP transport was flaky).

### Docs
- New `## LLM Resilience` section in `CLAUDE.md` (inserted before `## Project Skills`) with classification rules, env-var table, and alias note.

## Verification

### Test counts

| Run | Passed | Deselected | Notes |
|---|---|---|---|
| Baseline (before plan) | 902 | 2 | |
| After Task 1 (errors + config) | 902 | 2 | No new tests, no regressions |
| After Task 2 (helper + wire + tests) | 912 | 2 | +10 resilience tests, 0 regressions |
| After Task 3 (docs) | 912 | 2 | Final state |

### Resilience test coverage (`tests/test_llm_resilience.py`)

All 10 scenarios from the plan pass:

1. `test_single_200_no_retry` — happy path, 1 HTTP call, 0 sleeps.
2. `test_503_then_200_retries_once` — 1 retry, sleep ∈ [0.1, 0.15].
3. `test_3x_503_on_primary_falls_to_fallback_and_succeeds` — asserts per-call model field in request body; structlog captures `llm_model_fallback`.
4. `test_3x_503_primary_then_2x_503_fallback_then_200_on_fallback_attempt_3` — deep fallback, 6 calls total.
5. `test_429_honors_retry_after_seconds` — sleep contains `2.0` exactly.
6. `test_429_honors_retry_after_http_date` — sleep ≈ 3s (±1s tolerance).
7. `test_404_model_not_found_falls_through_immediately` — primary called exactly once, no sleeps, `reason="model_unavailable"` log.
8. `test_401_unauthorized_raises_immediately_no_retry_no_fallback` — 1 call total, `status_code=401` carried.
9. `test_all_models_exhaust_raises_final_error` — raises `LLMServiceUnavailableError`.
10. `test_vision_api_error_alias_backcompat` — identity + subclass + catch-via-alias.

### Pre-existing test health

- `tests/test_vision.py` — **24/24 pass** (fixture now uses `llm_retry_max_attempts=1` + empty fallbacks for fast runtime; behavior tests unchanged).
- `tests/brochure/schema_renderer/test_text_gen.py` — **23/23 pass** (OllamaTextClient.complete signature unchanged; retry helper is invisible to callers).
- `tests/brochure/schema_renderer/test_image_gate.py` — **12/12 pass**.
- `tests/test_errors.py` — 4/4 pass after updating `test_hierarchy_vision_errors` to reflect the VisionAPIError-as-alias contract (see Deviations).

## Decisions Made

- **`VisionAPIError = LLMAPIError` identity alias** (not subclass). Preserves every `except VisionAPIError` site because the identity preserves the catch relationship, AND new subclasses (`LLMTimeoutError`, etc.) are subclasses of `LLMAPIError` which IS `VisionAPIError`. Tradeoff: `VisionAPIError` is no longer a `VisionError` subclass. Only one test asserted that (test_errors.py) and it was updated to match the new contract.
- **500 classified as `LLMServiceUnavailableError` (retryable)** rather than non-retryable. Upstream Ollama regularly emits transient 500s that recover on immediate retry, and this keeps the existing `match="Ollama API error 500"` regex matching since the helper preserves that message shape on exhaustion.
- **Message shape preserved**: `f"Ollama API error {status}: {body[:200]}"` — ensures `test_ollama_evaluate_raises_on_http_error` keeps its regex match.
- **Helper returns parsed JSON dict**, not raw content string. Content extraction (`data["choices"][0]["message"]["content"]`) stays at the two call sites so the helper remains response-shape-agnostic.
- **Payloads no longer pre-set `"model"`**. The helper injects per-attempt. This deliberate interface shift simplifies the chain logic; callers pass `messages`, `max_tokens`, etc. and the helper appends the model dynamically.
- **Anthropic paths untouched**. The Anthropic SDK has its own retry logic; only the raw-httpx Ollama path needed hardening.
- **Non-retryable fatal detection** uses `type(err) is LLMAPIError` (exact type, not `isinstance`) so `LLMRateLimitError(status_code=401)` — which can't happen in practice but is defensively handled — wouldn't accidentally get fatal treatment. In practice only 400/401/403 produce bare `LLMAPIError` with the matching status, so this is correct.

## Deviations from Plan

### [Rule 1 - Bug] Fixed `tests/test_errors.py::test_hierarchy_vision_errors` regression
- **Found during:** Task 2 full test suite run (after wiring).
- **Issue:** The test asserted `issubclass(VisionAPIError, VisionError)`. After the planner-mandated `VisionAPIError = LLMAPIError` aliasing (LLMAPIError is a direct `FlyerGeneratorError` child, not `VisionError`), that assertion fails.
- **Fix:** Updated the test to match the new contract — assert `VisionAPIError is LLMAPIError` and `issubclass(VisionAPIError, FlyerGeneratorError)`. `VisionResponseParseError` still asserts its `VisionError` inheritance (unchanged). Added a code comment pointing at this quick task for traceability.
- **Files modified:** `tests/test_errors.py` (1 function body).
- **Commit:** b9e843b (bundled with Task 2).

### [Rule 3 - Blocker] Slowed-down vision tests
- **Found during:** Task 2 — `test_ollama_evaluate_raises_on_http_error` went from ~0.1s to 11s because respx's sticky 500 response triggered 3 primary retries + 3 fallback retries with real backoff waits.
- **Fix:** Overrode `llm_retry_max_attempts=1`, `llm_retry_base_delay=0.01`, `llm_retry_max_delay=0.01`, `ollama_vision_model_fallbacks=[]` in the shared `ollama_settings` fixture. Full retry/fallback behavior is exhaustively covered by `tests/test_llm_resilience.py` (which also uses sleep-patching, so even faster).
- **Result:** `tests/test_vision.py` runs in 1.75s (was 12.77s with default retry settings).
- **Files modified:** `tests/test_vision.py` (fixture only).
- **Commit:** b9e843b.

## Artifact Checklist

- [x] `flyer_generator/stages/llm_retry.py` exposes `_call_with_retry` + error classifiers
- [x] `flyer_generator/errors.py` has `LLMAPIError`, `LLMRateLimitError`, `LLMServiceUnavailableError`, `LLMTimeoutError`, `LLMModelUnavailableError` + `VisionAPIError = LLMAPIError` alias
- [x] `flyer_generator/config.py` has `ollama_text_model_fallbacks`, `ollama_vision_model_fallbacks`, `llm_retry_max_attempts`, `llm_retry_base_delay`, `llm_retry_max_delay`
- [x] Default fallback lists: `["kimi-k2.6:cloud", "qwen3.6:35b"]`
- [x] `tests/test_llm_resilience.py` exists with 10 scenarios
- [x] `python3 -m pytest tests/ -q -m "not slow"` → 912 passed (was 902 baseline + 10 new)
- [x] `tests/test_vision.py` passes (behavior unchanged; fixture tuned for speed)
- [x] `tests/brochure/schema_renderer/test_text_gen.py` + `test_image_gate.py` pass unchanged
- [x] `VisionAPIError` stays importable from `flyer_generator.errors` (alias)
- [x] No signature changes on `VisionEvaluator.evaluate`, `.evaluate_cover`, `OllamaTextClient.complete`, `AnthropicTextClient.complete`, or `build_text_client`
- [x] `## LLM Resilience` section in `CLAUDE.md` with env-var table
- [x] SUMMARY.md written

## Known Stubs

None. All new code paths have executable tests and real behavior.

## Self-Check: PASSED

- flyer_generator/stages/llm_retry.py — FOUND
- flyer_generator/errors.py modifications — FOUND (LLMAPIError, LLMRateLimitError, LLMServiceUnavailableError, LLMTimeoutError, LLMModelUnavailableError, VisionAPIError alias)
- flyer_generator/config.py modifications — FOUND (all 5 new fields)
- tests/test_llm_resilience.py — FOUND (10 tests pass)
- Commit 6ab79a9 — FOUND (feat: errors + config)
- Commit b9e843b — FOUND (feat: helper + wire + tests)
- Commit 2399991 — FOUND (docs: CLAUDE.md)

Full suite: 912 passed, 0 regressions from 902 baseline.
