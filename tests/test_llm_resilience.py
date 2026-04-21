"""Resilience tests for the shared LLM retry helper.

Covers backoff, Retry-After parsing, model-chain fallthrough, fatal errors,
and the VisionAPIError backwards-compat alias. See the helper at
flyer_generator/stages/llm_retry.py.
"""

from __future__ import annotations

import email.utils
import json
import time

import httpx
import pytest
import respx
import structlog

from flyer_generator.errors import (
    LLMAPIError,
    LLMModelUnavailableError,
    LLMRateLimitError,
    LLMServiceUnavailableError,
    LLMTimeoutError,
    VisionAPIError,
)
from flyer_generator.stages.llm_retry import _call_with_retry

BASE = "https://test-ollama.example.com"


# --------------------------------------------------------------------------- #
# Fixtures
# --------------------------------------------------------------------------- #


@pytest.fixture
def captured_sleeps(monkeypatch: pytest.MonkeyPatch) -> list[float]:
    calls: list[float] = []

    async def fake_sleep(delay: float) -> None:
        calls.append(delay)

    monkeypatch.setattr(
        "flyer_generator.stages.llm_retry.asyncio.sleep", fake_sleep
    )
    return calls


@pytest.fixture
async def client():
    async with httpx.AsyncClient(base_url=BASE, timeout=5.0) as c:
        yield c


def _ok(content: str = "hi") -> dict:
    return {
        "id": "chatcmpl-test",
        "object": "chat.completion",
        "choices": [
            {"index": 0, "message": {"role": "assistant", "content": content}}
        ],
    }


# --------------------------------------------------------------------------- #
# 1. Single 200 — no retry
# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
async def test_single_200_no_retry(
    client: httpx.AsyncClient, captured_sleeps: list[float]
) -> None:
    with respx.mock(base_url=BASE) as mock_api:
        route = mock_api.post("/v1/chat/completions").mock(
            return_value=httpx.Response(200, json=_ok("yes"))
        )

        data = await _call_with_retry(
            client,
            "/v1/chat/completions",
            {"messages": []},
            model_chain=["primary"],
            max_attempts=3,
            base_delay=0.1,
            max_delay=5.0,
        )
        assert data["choices"][0]["message"]["content"] == "yes"
        assert route.call_count == 1
        assert captured_sleeps == []


# --------------------------------------------------------------------------- #
# 2. 503 then 200 — retries once
# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
async def test_503_then_200_retries_once(
    client: httpx.AsyncClient, captured_sleeps: list[float]
) -> None:
    with respx.mock(base_url=BASE) as mock_api:
        route = mock_api.post("/v1/chat/completions").mock(
            side_effect=[
                httpx.Response(503, text="Service Unavailable"),
                httpx.Response(200, json=_ok("ok")),
            ]
        )

        data = await _call_with_retry(
            client,
            "/v1/chat/completions",
            {"messages": []},
            model_chain=["primary"],
            max_attempts=3,
            base_delay=0.1,
            max_delay=5.0,
        )
        assert data["choices"][0]["message"]["content"] == "ok"
        assert route.call_count == 2
        # One sleep captured, within [0.1, 0.1 * 1.5] = [0.1, 0.15]
        # Actually: base = min(max_delay, 0.1 * 2^0) = 0.1; jitter ∈ [0, 0.05]; total ∈ [0.1, 0.15]
        assert len(captured_sleeps) == 1
        assert 0.1 <= captured_sleeps[0] <= 0.15 + 1e-9


# --------------------------------------------------------------------------- #
# 3. 3x503 primary -> fallback succeeds
# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
async def test_3x_503_on_primary_falls_to_fallback_and_succeeds(
    client: httpx.AsyncClient, captured_sleeps: list[float]
) -> None:
    with respx.mock(base_url=BASE) as mock_api:
        route = mock_api.post("/v1/chat/completions").mock(
            side_effect=[
                httpx.Response(503),
                httpx.Response(503),
                httpx.Response(503),
                httpx.Response(200, json=_ok("via-fallback")),
            ]
        )

        with structlog.testing.capture_logs() as logs:
            data = await _call_with_retry(
                client,
                "/v1/chat/completions",
                {"messages": []},
                model_chain=["primary", "fallback-a"],
                max_attempts=3,
                base_delay=0.1,
                max_delay=5.0,
            )

        assert data["choices"][0]["message"]["content"] == "via-fallback"
        assert route.call_count == 4
        # Calls 1-3 use primary, call 4 uses fallback-a
        for i in (0, 1, 2):
            body = json.loads(route.calls[i].request.content)
            assert body["model"] == "primary", f"call {i} model mismatch"
        body4 = json.loads(route.calls[3].request.content)
        assert body4["model"] == "fallback-a"
        # llm_model_fallback logged
        assert any(e.get("event") == "llm_model_fallback" for e in logs), logs


# --------------------------------------------------------------------------- #
# 4. Deep fallback — 5 failures then success
# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
async def test_3x_503_primary_then_2x_503_fallback_then_200_on_fallback_attempt_3(
    client: httpx.AsyncClient, captured_sleeps: list[float]
) -> None:
    with respx.mock(base_url=BASE) as mock_api:
        route = mock_api.post("/v1/chat/completions").mock(
            side_effect=[
                httpx.Response(503),  # primary 1
                httpx.Response(503),  # primary 2
                httpx.Response(503),  # primary 3 (exhausts)
                httpx.Response(503),  # fallback 1
                httpx.Response(503),  # fallback 2
                httpx.Response(200, json=_ok("finally")),  # fallback 3 success
            ]
        )

        data = await _call_with_retry(
            client,
            "/v1/chat/completions",
            {"messages": []},
            model_chain=["primary", "fallback-a"],
            max_attempts=3,
            base_delay=0.1,
            max_delay=5.0,
        )

        assert data["choices"][0]["message"]["content"] == "finally"
        assert route.call_count == 6
        # Calls 0,1,2 primary ; 3,4,5 fallback
        for i in (0, 1, 2):
            assert json.loads(route.calls[i].request.content)["model"] == "primary"
        for i in (3, 4, 5):
            assert json.loads(route.calls[i].request.content)["model"] == "fallback-a"


# --------------------------------------------------------------------------- #
# 5. 429 Retry-After seconds
# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
async def test_429_honors_retry_after_seconds(
    client: httpx.AsyncClient, captured_sleeps: list[float]
) -> None:
    with respx.mock(base_url=BASE) as mock_api:
        mock_api.post("/v1/chat/completions").mock(
            side_effect=[
                httpx.Response(429, headers={"Retry-After": "2"}, text="slow down"),
                httpx.Response(200, json=_ok("ok")),
            ]
        )

        data = await _call_with_retry(
            client,
            "/v1/chat/completions",
            {"messages": []},
            model_chain=["primary"],
            max_attempts=3,
            base_delay=0.1,
            max_delay=10.0,
        )
        assert data["choices"][0]["message"]["content"] == "ok"
        assert 2.0 in captured_sleeps, captured_sleeps


# --------------------------------------------------------------------------- #
# 6. 429 Retry-After HTTP-date
# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
async def test_429_honors_retry_after_http_date(
    client: httpx.AsyncClient, captured_sleeps: list[float]
) -> None:
    http_date = email.utils.formatdate(time.time() + 3, usegmt=True)
    with respx.mock(base_url=BASE) as mock_api:
        mock_api.post("/v1/chat/completions").mock(
            side_effect=[
                httpx.Response(429, headers={"Retry-After": http_date}),
                httpx.Response(200, json=_ok("ok")),
            ]
        )

        await _call_with_retry(
            client,
            "/v1/chat/completions",
            {"messages": []},
            model_chain=["primary"],
            max_attempts=3,
            base_delay=0.1,
            max_delay=10.0,
        )

    assert len(captured_sleeps) == 1
    # Approximately 3 seconds (±1.0 tolerance for compute drift)
    assert 2.0 <= captured_sleeps[0] <= 4.0, captured_sleeps


# --------------------------------------------------------------------------- #
# 7. 404 model not found — advance immediately to fallback
# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
async def test_404_model_not_found_falls_through_immediately(
    client: httpx.AsyncClient, captured_sleeps: list[float]
) -> None:
    with respx.mock(base_url=BASE) as mock_api:
        route = mock_api.post("/v1/chat/completions").mock(
            side_effect=[
                httpx.Response(
                    404, json={"error": "model 'llama3.2' not found"}
                ),
                httpx.Response(200, json=_ok("fallback ok")),
            ]
        )

        with structlog.testing.capture_logs() as logs:
            data = await _call_with_retry(
                client,
                "/v1/chat/completions",
                {"messages": []},
                model_chain=["primary", "fallback-a"],
                max_attempts=3,
                base_delay=0.1,
                max_delay=5.0,
            )

        assert data["choices"][0]["message"]["content"] == "fallback ok"
        # Primary tried once, fallback tried once (no retries on primary)
        assert route.call_count == 2
        assert json.loads(route.calls[0].request.content)["model"] == "primary"
        assert json.loads(route.calls[1].request.content)["model"] == "fallback-a"
        # No sleeps — we did not retry the primary
        assert captured_sleeps == []
        # Fallback log with model_unavailable reason
        fallback_events = [
            e
            for e in logs
            if e.get("event") == "llm_model_fallback"
            and e.get("reason") == "model_unavailable"
        ]
        assert fallback_events, logs


# --------------------------------------------------------------------------- #
# 8. 401 unauthorized — raise immediately, no retry, no fallback
# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
async def test_401_unauthorized_raises_immediately_no_retry_no_fallback(
    client: httpx.AsyncClient, captured_sleeps: list[float]
) -> None:
    with respx.mock(base_url=BASE) as mock_api:
        route = mock_api.post("/v1/chat/completions").mock(
            return_value=httpx.Response(401, text="Unauthorized")
        )

        with pytest.raises(LLMAPIError) as excinfo:
            await _call_with_retry(
                client,
                "/v1/chat/completions",
                {"messages": []},
                model_chain=["primary", "fallback-a"],
                max_attempts=3,
                base_delay=0.1,
                max_delay=5.0,
            )

        # Must NOT be a rate-limit or service-unavailable subclass
        assert not isinstance(excinfo.value, LLMRateLimitError)
        assert not isinstance(excinfo.value, LLMServiceUnavailableError)
        # Only one call — no retries, no fallback
        assert route.call_count == 1
        # First call used primary model
        assert json.loads(route.calls[0].request.content)["model"] == "primary"
        assert captured_sleeps == []
        # status_code carried
        assert excinfo.value.status_code == 401


# --------------------------------------------------------------------------- #
# 9. Chain exhaustion — raise last error
# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
async def test_all_models_exhaust_raises_final_error(
    client: httpx.AsyncClient, captured_sleeps: list[float]
) -> None:
    with respx.mock(base_url=BASE) as mock_api:
        mock_api.post("/v1/chat/completions").mock(
            return_value=httpx.Response(503, text="nope")
        )

        with pytest.raises(LLMServiceUnavailableError) as excinfo:
            await _call_with_retry(
                client,
                "/v1/chat/completions",
                {"messages": []},
                model_chain=["primary", "fb-a"],
                max_attempts=2,
                base_delay=0.1,
                max_delay=5.0,
            )

        assert "503" in str(excinfo.value)
        assert excinfo.value.status_code == 503


# --------------------------------------------------------------------------- #
# 10. VisionAPIError backwards-compatible alias
# --------------------------------------------------------------------------- #


def test_vision_api_error_alias_backcompat() -> None:
    # Identity check
    assert VisionAPIError is LLMAPIError
    # Subclass relationships
    assert issubclass(LLMTimeoutError, VisionAPIError)
    assert issubclass(LLMRateLimitError, VisionAPIError)
    assert issubclass(LLMServiceUnavailableError, VisionAPIError)
    assert issubclass(LLMModelUnavailableError, VisionAPIError)

    # Raise subclass, catch with legacy name
    caught = False
    try:
        raise LLMTimeoutError("timed out")
    except VisionAPIError as exc:
        caught = True
        assert "timed out" in str(exc)
    assert caught
