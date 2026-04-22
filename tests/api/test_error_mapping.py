"""Exception-handler bank tests. Verifies every domain error maps to the right HTTP status."""

from __future__ import annotations

import pytest
from fastapi import APIRouter

from flyer_generator.errors import (
    BrandKitContrastError,
    BrandKitNotFoundError,
    BrandKitScrapeError,
    BrandVoiceViolationError,
    ComfyJobTimeoutError,
    ComfySubmitError,
    ConfigurationError,
    LLMAPIError,
    LLMRateLimitError,
    SocialError,
    VisionAPIError,
)


def _register_error_route(app, exc: Exception, path: str = "/api/v1/_test_err") -> None:
    router = APIRouter()

    @router.get(path)
    async def _boom():
        raise exc

    app.include_router(router)


@pytest.mark.asyncio
async def test_brand_kit_not_found_maps_to_404(app, client) -> None:
    _register_error_route(
        app, BrandKitNotFoundError("kit 'x' not found", slug="x", expected_path="/tmp/x")
    )
    r = await client.get("/api/v1/_test_err")
    assert r.status_code == 404
    body = r.json()
    assert body["error_type"] == "BrandKitNotFoundError"
    assert body["detail"] == "kit 'x' not found"
    assert "trace_id" in body
    # Context bag must NOT leak — no 'slug' or 'expected_path' in response body.
    assert "slug" not in body
    assert "expected_path" not in body


@pytest.mark.asyncio
async def test_brand_kit_scrape_error_maps_to_400(app, client) -> None:
    _register_error_route(app, BrandKitScrapeError("ssrf blocked"))
    r = await client.get("/api/v1/_test_err")
    assert r.status_code == 400
    assert r.json()["error_type"] == "BrandKitScrapeError"


@pytest.mark.asyncio
async def test_brand_kit_contrast_error_maps_to_400(app, client) -> None:
    _register_error_route(app, BrandKitContrastError("no passing swap"))
    r = await client.get("/api/v1/_test_err")
    assert r.status_code == 400
    assert r.json()["error_type"] == "BrandKitContrastError"


@pytest.mark.asyncio
async def test_brand_voice_violation_maps_to_422(app, client) -> None:
    _register_error_route(app, BrandVoiceViolationError("banned word: x"))
    r = await client.get("/api/v1/_test_err")
    assert r.status_code == 422
    assert r.json()["error_type"] == "BrandVoiceViolationError"


@pytest.mark.asyncio
async def test_comfy_error_maps_to_502(app, client) -> None:
    _register_error_route(app, ComfySubmitError("502 from upstream"))
    r = await client.get("/api/v1/_test_err")
    assert r.status_code == 502


@pytest.mark.asyncio
async def test_comfy_timeout_maps_to_502(app, client) -> None:
    _register_error_route(
        app, ComfyJobTimeoutError("poll exhausted", prompt_id="p", attempts=10)
    )
    r = await client.get("/api/v1/_test_err")
    assert r.status_code == 502


@pytest.mark.asyncio
async def test_llm_api_error_maps_to_502(app, client) -> None:
    _register_error_route(app, LLMAPIError("503 from ollama"))
    r = await client.get("/api/v1/_test_err")
    assert r.status_code == 502


@pytest.mark.asyncio
async def test_vision_api_error_alias_maps_to_502(app, client) -> None:
    # VisionAPIError is an alias for LLMAPIError — same 502 target.
    _register_error_route(app, VisionAPIError("bad vision response"))
    r = await client.get("/api/v1/_test_err")
    assert r.status_code == 502


@pytest.mark.asyncio
async def test_rate_limit_maps_to_503_with_retry_after(app, client) -> None:
    _register_error_route(
        app, LLMRateLimitError("429 from provider", retry_after_seconds=5.0)
    )
    r = await client.get("/api/v1/_test_err")
    assert r.status_code == 503
    assert r.headers.get("Retry-After") == "5"
    assert r.json()["error_type"] == "LLMRateLimitError"


@pytest.mark.asyncio
async def test_social_error_maps_to_400(app, client) -> None:
    _register_error_route(app, SocialError("bad platform"))
    r = await client.get("/api/v1/_test_err")
    assert r.status_code == 400
    assert r.json()["error_type"] == "SocialError"


@pytest.mark.asyncio
async def test_configuration_error_maps_to_400(app, client) -> None:
    # ConfigurationError subclasses FlyerGeneratorError — catch-all path (400)
    _register_error_route(app, ConfigurationError("missing key"))
    r = await client.get("/api/v1/_test_err")
    assert r.status_code == 400


@pytest.mark.asyncio
async def test_body_shape_has_trace_id(app, client) -> None:
    _register_error_route(app, BrandKitNotFoundError("x"))
    r = await client.get(
        "/api/v1/_test_err", headers={"X-Request-ID": "01HTRACE" + "A" * 18}
    )
    body = r.json()
    assert body["trace_id"] == "01HTRACE" + "A" * 18
