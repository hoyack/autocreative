"""Tests for OllamaTextClient and AnthropicTextClient."""

from __future__ import annotations

import json
from types import SimpleNamespace
from unittest.mock import AsyncMock

import httpx
import pytest
from pydantic import SecretStr

from flyer_generator.brochure.llm_client import (
    AnthropicTextClient,
    OllamaTextClient,
    build_text_client,
)
from flyer_generator.config import Settings
from flyer_generator.errors import VisionAPIError, VisionResponseParseError


def _ollama_settings() -> Settings:
    return Settings(
        anthropic_api_key=SecretStr("sk-test"),
        comfycloud_api_key=SecretStr("t"),
        vision_provider="ollama",
        ollama_api_key=SecretStr("ol-test"),
        ollama_base_url="https://ollama.test",
        ollama_text_model="llama3.2",
    )


def _anthropic_settings() -> Settings:
    return Settings(
        anthropic_api_key=SecretStr("sk-test"),
        comfycloud_api_key=SecretStr("t"),
        vision_provider="anthropic",
        vision_model="claude-sonnet-4-6",
    )


def _ollama_ok_response(content: str) -> httpx.Response:
    return httpx.Response(
        200,
        json={"choices": [{"message": {"content": content}}]},
    )


# ---------- build_text_client factory ----------


def test_build_text_client_picks_ollama_for_ollama_provider() -> None:
    client = build_text_client(_ollama_settings())
    assert isinstance(client, OllamaTextClient)


def test_build_text_client_picks_anthropic_for_anthropic_provider() -> None:
    client = build_text_client(_anthropic_settings())
    assert isinstance(client, AnthropicTextClient)


# ---------- OllamaTextClient ----------


@pytest.mark.asyncio
async def test_ollama_text_complete_returns_stripped_text() -> None:
    transport = httpx.MockTransport(
        lambda request: _ollama_ok_response("  Hello world  ")
    )
    http = httpx.AsyncClient(transport=transport, base_url="https://ollama.test")
    client = OllamaTextClient(_ollama_settings(), http_client=http)

    result = await client.complete(system="sys", user="usr")
    assert result == "Hello world"


@pytest.mark.asyncio
async def test_ollama_text_json_mode_extracts_object() -> None:
    body = '```json\n{"key": "value"}\n```'
    transport = httpx.MockTransport(lambda request: _ollama_ok_response(body))
    http = httpx.AsyncClient(transport=transport, base_url="https://ollama.test")
    client = OllamaTextClient(_ollama_settings(), http_client=http)

    result = await client.complete(system="sys", user="usr", response_format="json")
    assert json.loads(result) == {"key": "value"}


@pytest.mark.asyncio
async def test_ollama_text_json_mode_retries_on_parse_failure() -> None:
    call_count = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        call_count["n"] += 1
        if call_count["n"] == 1:
            return _ollama_ok_response("no json here")
        return _ollama_ok_response('{"ok": true}')

    transport = httpx.MockTransport(handler)
    http = httpx.AsyncClient(transport=transport, base_url="https://ollama.test")
    client = OllamaTextClient(_ollama_settings(), http_client=http)

    result = await client.complete(system="sys", user="usr", response_format="json")
    assert json.loads(result) == {"ok": True}
    assert call_count["n"] == 2


@pytest.mark.asyncio
async def test_ollama_text_raises_on_http_error() -> None:
    transport = httpx.MockTransport(
        lambda request: httpx.Response(500, text="server error")
    )
    http = httpx.AsyncClient(transport=transport, base_url="https://ollama.test")
    client = OllamaTextClient(_ollama_settings(), http_client=http)

    with pytest.raises(VisionAPIError, match="500"):
        await client.complete(system="sys", user="usr")


@pytest.mark.asyncio
async def test_ollama_text_json_mode_raises_after_retry_fails() -> None:
    transport = httpx.MockTransport(lambda request: _ollama_ok_response("still no json"))
    http = httpx.AsyncClient(transport=transport, base_url="https://ollama.test")
    client = OllamaTextClient(_ollama_settings(), http_client=http)

    with pytest.raises(VisionResponseParseError):
        await client.complete(system="sys", user="usr", response_format="json")


# ---------- AnthropicTextClient ----------


@pytest.mark.asyncio
async def test_anthropic_text_complete(monkeypatch: pytest.MonkeyPatch) -> None:
    mock_client = SimpleNamespace(
        messages=SimpleNamespace(
            create=AsyncMock(
                return_value=SimpleNamespace(content=[SimpleNamespace(text="  hi ")])
            )
        )
    )
    monkeypatch.setattr(
        "flyer_generator.brochure.llm_client.AsyncAnthropic",
        lambda *args, **kwargs: mock_client,
    )

    client = AnthropicTextClient(_anthropic_settings())
    result = await client.complete(system="sys", user="usr")
    assert result == "hi"


@pytest.mark.asyncio
async def test_anthropic_text_json_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    mock_client = SimpleNamespace(
        messages=SimpleNamespace(
            create=AsyncMock(
                return_value=SimpleNamespace(
                    content=[SimpleNamespace(text='{"ok": 1}')]
                )
            )
        )
    )
    monkeypatch.setattr(
        "flyer_generator.brochure.llm_client.AsyncAnthropic",
        lambda *args, **kwargs: mock_client,
    )

    client = AnthropicTextClient(_anthropic_settings())
    result = await client.complete(system="sys", user="usr", response_format="json")
    assert json.loads(result) == {"ok": 1}
