"""Smoke tests: app boots, OpenAPI renders, healthz + request-id + CORS."""

from __future__ import annotations

import pytest


@pytest.mark.asyncio
async def test_healthz(client) -> None:
    r = await client.get("/healthz")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


@pytest.mark.asyncio
async def test_docs_ui_served(client) -> None:
    r = await client.get("/docs")
    assert r.status_code == 200
    # FastAPI's Swagger UI page contains this token
    assert b"swagger-ui" in r.content.lower() or b"Swagger UI" in r.content


@pytest.mark.asyncio
async def test_openapi_json_served(client) -> None:
    r = await client.get("/openapi.json")
    assert r.status_code == 200
    body = r.json()
    assert body["info"]["title"] == "flyer-generator API"
    assert body["info"]["version"] == "0.1.0"


@pytest.mark.asyncio
async def test_unknown_path_returns_404(client) -> None:
    r = await client.get("/api/v1/this-does-not-exist")
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_request_id_echoed_when_supplied(client) -> None:
    # Incoming X-Request-ID should be echoed on the response.
    r = await client.get(
        "/healthz", headers={"X-Request-ID": "01HTEST" + "A" * 19}
    )
    assert r.headers.get("X-Request-ID") == "01HTEST" + "A" * 19


@pytest.mark.asyncio
async def test_request_id_generated_when_missing(client) -> None:
    r = await client.get("/healthz")
    # asgi-correlation-id generates a UUID4 when no header present
    xid = r.headers.get("X-Request-ID", "")
    assert len(xid) >= 8  # UUID4 is 36 chars


@pytest.mark.asyncio
async def test_cors_allowed_origin(client) -> None:
    r = await client.get(
        "/healthz", headers={"Origin": "http://localhost:5173"}
    )
    assert r.headers.get("access-control-allow-origin") == "http://localhost:5173"


@pytest.mark.asyncio
async def test_cors_disallowed_origin(client) -> None:
    r = await client.get("/healthz", headers={"Origin": "http://evil.example"})
    # Starlette CORS middleware does NOT add Access-Control-Allow-Origin for
    # origins not in allow_origins — the request still succeeds but without CORS headers.
    assert "access-control-allow-origin" not in r.headers
