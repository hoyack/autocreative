"""Shared retry + model-fallback wrapper for Ollama/OpenAI-compatible HTTP calls.

Used by:
  - flyer_generator.stages.vision.VisionEvaluator._post_ollama (vision path)
  - flyer_generator.brochure.llm_client.OllamaTextClient._call (text path)

Classification rules (see also flyer_generator.errors):
  - httpx.HTTPStatusError where status == 429 -> LLMRateLimitError, RETRYABLE,
    honor Retry-After header (integer seconds OR HTTP-date; clamped to max_delay).
  - status in (500, 502, 503)                 -> LLMServiceUnavailableError, RETRYABLE.
  - status == 404 OR body contains "model"
    + "not found" / "not loaded"              -> LLMModelUnavailableError,
                                                  NOT retryable on same model;
                                                  chain advances to next model.
  - status in (400, 401, 403)                 -> LLMAPIError, NOT retryable,
                                                  NOT model-fallback-eligible.
  - httpx.ReadTimeout / ConnectTimeout /
    ConnectError / ReadError                  -> LLMTimeoutError, RETRYABLE.
  - other httpx.HTTPError                     -> LLMAPIError, RETRYABLE (one try
                                                  on same model, then advance).

Backoff: delay = min(max_delay, base_delay * 2**(attempt-1)) + uniform(0, base_delay*0.5).
"""

from __future__ import annotations

import asyncio
import email.utils
import json
import random
from datetime import datetime, timezone
from typing import Any

import httpx
import structlog

from flyer_generator.errors import (
    LLMAPIError,
    LLMModelUnavailableError,
    LLMRateLimitError,
    LLMServiceUnavailableError,
    LLMTimeoutError,
)

logger = structlog.get_logger()

_MODEL_NOT_FOUND_TOKENS = ("not found", "not loaded", "unknown model")


def _parse_retry_after(value: str | None, *, max_delay: float) -> float | None:
    """Parse a Retry-After header (seconds integer OR HTTP-date). Clamp to max_delay."""
    if not value:
        return None
    v = value.strip()
    try:
        seconds = float(v)
        return min(max_delay, max(0.0, seconds))
    except ValueError:
        pass
    try:
        target = email.utils.parsedate_to_datetime(v)
    except (TypeError, ValueError):
        return None
    if target is None:
        return None
    if target.tzinfo is None:
        target = target.replace(tzinfo=timezone.utc)
    delta = (target - datetime.now(timezone.utc)).total_seconds()
    if delta < 0:
        return 0.0
    return min(max_delay, delta)


def _looks_like_model_unavailable(body: str) -> bool:
    low = body.lower()
    if "model" not in low:
        return False
    return any(tok in low for tok in _MODEL_NOT_FOUND_TOKENS)


def _classify_status_error(
    exc: httpx.HTTPStatusError, *, model: str, max_delay: float
) -> LLMAPIError:
    """Convert an httpx.HTTPStatusError into the appropriate LLMAPIError subclass."""
    status = exc.response.status_code
    body = exc.response.text or ""
    msg_body = body[:200]
    # Preserve legacy message shape for existing test: "Ollama API error {status}: {body}"
    base_msg = f"Ollama API error {status}: {msg_body}"
    if status == 429:
        retry_after = _parse_retry_after(
            exc.response.headers.get("retry-after"), max_delay=max_delay
        )
        return LLMRateLimitError(
            base_msg, retry_after_seconds=retry_after, model=model, status_code=status
        )
    if status in (500, 502, 503):
        return LLMServiceUnavailableError(base_msg, model=model, status_code=status)
    if status == 404 or _looks_like_model_unavailable(body):
        return LLMModelUnavailableError(base_msg, model=model, status_code=status)
    if status in (400, 401, 403):
        return LLMAPIError(base_msg, model=model, status_code=status)
    # Any other 4xx/5xx: wrap as generic LLMAPIError
    return LLMAPIError(base_msg, model=model, status_code=status)


def _classify_network_error(exc: httpx.HTTPError, *, model: str) -> LLMAPIError:
    if isinstance(
        exc, (httpx.ReadTimeout, httpx.ConnectTimeout, httpx.ConnectError, httpx.ReadError)
    ):
        return LLMTimeoutError(str(exc) or type(exc).__name__, model=model)
    return LLMAPIError(str(exc) or type(exc).__name__, model=model)


def _compute_backoff(attempt: int, base_delay: float, max_delay: float) -> float:
    """Exponential backoff + jitter. attempt is 1-indexed."""
    base = min(max_delay, base_delay * (2 ** (attempt - 1)))
    jitter = random.uniform(0.0, base_delay * 0.5)
    return min(max_delay, base + jitter)


async def _call_with_retry(
    http_client: httpx.AsyncClient,
    url: str,
    payload: dict[str, Any],
    *,
    model_chain: list[str],
    max_attempts: int,
    base_delay: float,
    max_delay: float,
    log: Any | None = None,
) -> dict[str, Any]:
    """POST `payload` to `url`, retrying transient failures and falling through models.

    Iterates `model_chain`. For each model:
      - Attempt up to `max_attempts` times.
      - On retryable errors: sleep with exponential backoff + jitter; on 429 honor Retry-After.
      - On fatal errors (LLMModelUnavailableError or 400/401/403): break inner loop.
        - 400/401/403: abort entire chain (raise immediately).
        - model_unavailable: advance to next model in chain.
      - On success: return parsed JSON body.

    If the entire chain exhausts, raise the last-seen LLMAPIError subclass.
    """
    if not model_chain:
        raise LLMAPIError("model_chain is empty")

    log = log or logger
    last_error: LLMAPIError | None = None

    for model_idx, model in enumerate(model_chain):
        call_payload = {**payload, "model": model}
        for attempt in range(1, max_attempts + 1):
            bound = log.bind(model=model, attempt=attempt, max_attempts=max_attempts)
            try:
                resp = await http_client.post(url, json=call_payload)
                resp.raise_for_status()
                try:
                    return resp.json()
                except json.JSONDecodeError as exc:
                    # 200 with bad JSON: not retryable, not fallback-eligible.
                    raise LLMAPIError(
                        f"Unexpected Ollama response format: {resp.text[:200]}",
                        model=model,
                        status_code=resp.status_code,
                    ) from exc
            except httpx.HTTPStatusError as exc:
                err = _classify_status_error(exc, model=model, max_delay=max_delay)
                last_error = err
                if isinstance(err, LLMModelUnavailableError):
                    next_model = (
                        model_chain[model_idx + 1]
                        if model_idx + 1 < len(model_chain)
                        else None
                    )
                    bound.warning(
                        "llm_model_fallback",
                        from_=model,
                        to=next_model,
                        reason="model_unavailable",
                        status=err.status_code,
                    )
                    break  # advance chain
                if (
                    type(err) is LLMAPIError
                    and err.status_code in (400, 401, 403)
                ):
                    # Real client error — abort entire chain.
                    raise err
                # Retryable (429 / 500 / 502 / 503). Sleep and retry same model.
                if attempt < max_attempts:
                    if (
                        isinstance(err, LLMRateLimitError)
                        and err.retry_after_seconds is not None
                    ):
                        delay = err.retry_after_seconds
                    else:
                        delay = _compute_backoff(attempt, base_delay, max_delay)
                    bound.warning(
                        "llm_retry",
                        status=err.status_code,
                        delay=delay,
                        error_type=type(err).__name__,
                    )
                    await asyncio.sleep(delay)
                    continue
                # max_attempts exhausted on this model; fall through chain
                if model_idx + 1 < len(model_chain):
                    bound.warning(
                        "llm_model_fallback",
                        from_=model,
                        to=model_chain[model_idx + 1],
                        reason=f"exhausted_{type(err).__name__}",
                    )
                break
            except httpx.HTTPError as exc:
                err = _classify_network_error(exc, model=model)
                last_error = err
                if attempt < max_attempts:
                    delay = _compute_backoff(attempt, base_delay, max_delay)
                    bound.warning(
                        "llm_retry",
                        delay=delay,
                        error_type=type(err).__name__,
                    )
                    await asyncio.sleep(delay)
                    continue
                if model_idx + 1 < len(model_chain):
                    bound.warning(
                        "llm_model_fallback",
                        from_=model,
                        to=model_chain[model_idx + 1],
                        reason=f"exhausted_{type(err).__name__}",
                    )
                break

    assert last_error is not None  # reachable only after at least one failure
    raise last_error
