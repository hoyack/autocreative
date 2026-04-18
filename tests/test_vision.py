"""Comprehensive tests for VisionEvaluator stage."""

from __future__ import annotations

import io
import json
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
import respx
from anthropic import APIError
from PIL import Image

from flyer_generator.config import Settings
from flyer_generator.errors import VisionAPIError, VisionResponseParseError
from flyer_generator.models import ComfyJob, EventInput, GeneratedBackground, VisionVerdict
from flyer_generator.stages.vision import VISION_SYSTEM_PROMPT, VisionEvaluator
from tests.fixtures.vision_responses import (
    APPROVED_RESPONSE,
    INVALID_ZONE_RESPONSE,
    LOW_CONFIDENCE_RESPONSE,
    MARKDOWN_WRAPPED,
    NULL_ZONES_APPROVED_RESPONSE,
    PROSE_WRAPPED,
    REJECTED_RESPONSE,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def settings() -> Settings:
    return Settings(
        vision_provider="anthropic",
        anthropic_api_key="test-key",
        vision_model="claude-sonnet-4-5",
        vision_max_tokens=1024,
        vision_timeout_seconds=30,
        vision_confidence_threshold=0.6,
    )


@pytest.fixture
def mock_background() -> GeneratedBackground:
    img = Image.new("RGB", (1080, 1920), (128, 64, 32))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    job = ComfyJob(
        prompt_id="test-123",
        submitted_at=datetime.now(timezone.utc),
        positive_prompt="test",
        negative_prompt="test",
        seed=42,
        attempt_number=1,
    )
    return GeneratedBackground(
        image_bytes=buf.getvalue(),
        source_dimensions=(832, 1472),
        final_dimensions=(1080, 1920),
        comfy_job=job,
    )


@pytest.fixture
def mock_event() -> EventInput:
    return EventInput(
        title="Jazz Night",
        date="2026-05-01",
        time="7 PM",
        location_name="Blue Note",
        location_address="123 Jazz St",
        fees="$25",
        org="Jazz Society",
        style_concept="jazz club atmosphere",
        style_preset="photorealistic",
    )


def _mock_response(text: str) -> MagicMock:
    """Create a mock Anthropic response."""
    mock = MagicMock()
    mock.content = [MagicMock(text=text)]
    return mock


# ---------------------------------------------------------------------------
# System prompt tests
# ---------------------------------------------------------------------------


class TestSystemPrompt:
    def test_system_prompt_contains_required_elements(self) -> None:
        required = [
            "3x3 grid",
            "APPROPRIATENESS",
            "LAYOUT",
            "TITLE",
            "DETAILS",
            "FEE_BADGE",
            "ORG_CREDIT",
            "approved",
            "confidence",
            "zones",
            "text_color",
        ]
        for element in required:
            assert element in VISION_SYSTEM_PROMPT, f"Missing: {element}"


# ---------------------------------------------------------------------------
# Parsing tests (_parse_and_validate)
# ---------------------------------------------------------------------------


class TestParsing:
    def test_parse_clean_json(self, settings: Settings) -> None:
        evaluator = VisionEvaluator(settings)
        raw = json.dumps(APPROVED_RESPONSE)
        verdict = evaluator._parse_and_validate(raw)
        assert isinstance(verdict, VisionVerdict)
        assert verdict.approved is True
        assert verdict.confidence == 0.85

    def test_parse_markdown_wrapped(self, settings: Settings) -> None:
        evaluator = VisionEvaluator(settings)
        verdict = evaluator._parse_and_validate(MARKDOWN_WRAPPED)
        assert isinstance(verdict, VisionVerdict)
        assert verdict.approved is True

    def test_parse_prose_wrapped(self, settings: Settings) -> None:
        evaluator = VisionEvaluator(settings)
        verdict = evaluator._parse_and_validate(PROSE_WRAPPED)
        assert isinstance(verdict, VisionVerdict)
        assert verdict.approved is True

    def test_parse_invalid_json_raises(self, settings: Settings) -> None:
        evaluator = VisionEvaluator(settings)
        with pytest.raises(VisionResponseParseError, match="Invalid JSON"):
            evaluator._parse_and_validate("{not valid json at all!!}")

    def test_parse_no_json_object_raises(self, settings: Settings) -> None:
        evaluator = VisionEvaluator(settings)
        with pytest.raises(VisionResponseParseError, match="No JSON object found"):
            evaluator._parse_and_validate("No braces here at all")


# ---------------------------------------------------------------------------
# Confidence gate tests
# ---------------------------------------------------------------------------


class TestConfidenceGate:
    def test_confidence_gate_flips_approved(self, settings: Settings) -> None:
        evaluator = VisionEvaluator(settings)
        raw = json.dumps(LOW_CONFIDENCE_RESPONSE)
        verdict = evaluator._parse_and_validate(raw)
        assert verdict.approved is False

    def test_confidence_gate_adds_rejection_reason(self, settings: Settings) -> None:
        evaluator = VisionEvaluator(settings)
        raw = json.dumps(LOW_CONFIDENCE_RESPONSE)
        verdict = evaluator._parse_and_validate(raw)
        assert any("Low confidence: 0.45" in r for r in verdict.rejection_reasons)

    def test_confidence_gate_passes_above_threshold(self, settings: Settings) -> None:
        evaluator = VisionEvaluator(settings)
        raw = json.dumps(APPROVED_RESPONSE)
        verdict = evaluator._parse_and_validate(raw)
        assert verdict.approved is True
        assert verdict.confidence == 0.85


# ---------------------------------------------------------------------------
# Zone validation tests
# ---------------------------------------------------------------------------


class TestZoneValidation:
    def test_zone_validation_rejects_invalid_zone_name(self, settings: Settings) -> None:
        evaluator = VisionEvaluator(settings)
        raw = json.dumps(INVALID_ZONE_RESPONSE)
        verdict = evaluator._parse_and_validate(raw)
        assert verdict.approved is False
        assert any("Invalid zone" in r for r in verdict.rejection_reasons)

    def test_zone_validation_rejects_null_zones_when_approved(
        self, settings: Settings
    ) -> None:
        evaluator = VisionEvaluator(settings)
        raw = json.dumps(NULL_ZONES_APPROVED_RESPONSE)
        verdict = evaluator._parse_and_validate(raw)
        assert verdict.approved is False
        assert any("Zones missing" in r for r in verdict.rejection_reasons)

    def test_zone_validation_passes_valid_zones(self, settings: Settings) -> None:
        evaluator = VisionEvaluator(settings)
        raw = json.dumps(APPROVED_RESPONSE)
        verdict = evaluator._parse_and_validate(raw)
        assert verdict.approved is True
        assert verdict.zones is not None
        assert verdict.zones.title == "TOP_CENTER"


# ---------------------------------------------------------------------------
# Evaluate method tests (mock SDK)
# ---------------------------------------------------------------------------


class TestEvaluate:
    @pytest.mark.asyncio
    async def test_evaluate_sends_correct_message_structure(
        self,
        settings: Settings,
        mock_background: GeneratedBackground,
        mock_event: EventInput,
    ) -> None:
        with patch("flyer_generator.stages.vision.AsyncAnthropic") as mock_cls:
            mock_client = MagicMock()
            mock_client.messages = MagicMock()
            mock_client.messages.create = AsyncMock(
                return_value=_mock_response(json.dumps(APPROVED_RESPONSE))
            )
            mock_cls.return_value = mock_client

            evaluator = VisionEvaluator(settings)
            await evaluator.evaluate(mock_background, mock_event)

            call_kwargs = mock_client.messages.create.call_args[1]
            assert call_kwargs["system"] == VISION_SYSTEM_PROMPT
            user_msg = call_kwargs["messages"][0]
            assert user_msg["role"] == "user"
            # Should have image block + text block
            content = user_msg["content"]
            assert len(content) == 2
            assert content[0]["type"] == "image"
            assert content[1]["type"] == "text"

    @pytest.mark.asyncio
    async def test_evaluate_returns_verdict_on_success(
        self,
        settings: Settings,
        mock_background: GeneratedBackground,
        mock_event: EventInput,
    ) -> None:
        with patch("flyer_generator.stages.vision.AsyncAnthropic") as mock_cls:
            mock_client = MagicMock()
            mock_client.messages = MagicMock()
            mock_client.messages.create = AsyncMock(
                return_value=_mock_response(json.dumps(APPROVED_RESPONSE))
            )
            mock_cls.return_value = mock_client

            evaluator = VisionEvaluator(settings)
            verdict = await evaluator.evaluate(mock_background, mock_event)

            assert isinstance(verdict, VisionVerdict)
            assert verdict.approved is True
            assert verdict.confidence == 0.85

    @pytest.mark.asyncio
    async def test_evaluate_retries_on_parse_failure(
        self,
        settings: Settings,
        mock_background: GeneratedBackground,
        mock_event: EventInput,
    ) -> None:
        with patch("flyer_generator.stages.vision.AsyncAnthropic") as mock_cls:
            mock_client = MagicMock()
            mock_client.messages = MagicMock()
            # First call returns garbled, second returns valid JSON
            mock_client.messages.create = AsyncMock(
                side_effect=[
                    _mock_response("This is not JSON at all, sorry!"),
                    _mock_response(json.dumps(APPROVED_RESPONSE)),
                ]
            )
            mock_cls.return_value = mock_client

            evaluator = VisionEvaluator(settings)
            verdict = await evaluator.evaluate(mock_background, mock_event)

            assert isinstance(verdict, VisionVerdict)
            assert verdict.approved is True
            # Verify retry was called (2 calls total)
            assert mock_client.messages.create.call_count == 2
            # Verify retry message includes "Return valid JSON only"
            retry_kwargs = mock_client.messages.create.call_args_list[1][1]
            last_user_msg = retry_kwargs["messages"][-1]
            assert last_user_msg["content"] == "Return valid JSON only, no prose."

    @pytest.mark.asyncio
    async def test_evaluate_raises_after_retry_fails(
        self,
        settings: Settings,
        mock_background: GeneratedBackground,
        mock_event: EventInput,
    ) -> None:
        with patch("flyer_generator.stages.vision.AsyncAnthropic") as mock_cls:
            mock_client = MagicMock()
            mock_client.messages = MagicMock()
            # Both calls return garbled text
            mock_client.messages.create = AsyncMock(
                side_effect=[
                    _mock_response("Garbled nonsense no JSON here"),
                    _mock_response("Still garbled, no braces anywhere"),
                ]
            )
            mock_cls.return_value = mock_client

            evaluator = VisionEvaluator(settings)
            with pytest.raises(VisionResponseParseError):
                await evaluator.evaluate(mock_background, mock_event)

    @pytest.mark.asyncio
    async def test_evaluate_raises_vision_api_error_on_sdk_error(
        self,
        settings: Settings,
        mock_background: GeneratedBackground,
        mock_event: EventInput,
    ) -> None:
        with patch("flyer_generator.stages.vision.AsyncAnthropic") as mock_cls:
            mock_client = MagicMock()
            mock_client.messages = MagicMock()
            mock_client.messages.create = AsyncMock(
                side_effect=APIError(
                    message="Internal Server Error",
                    request=MagicMock(),
                    body=None,
                )
            )
            mock_cls.return_value = mock_client

            evaluator = VisionEvaluator(settings)
            with pytest.raises(VisionAPIError):
                await evaluator.evaluate(mock_background, mock_event)

    @pytest.mark.asyncio
    async def test_evaluate_returns_rejected_verdict(
        self,
        settings: Settings,
        mock_background: GeneratedBackground,
        mock_event: EventInput,
    ) -> None:
        with patch("flyer_generator.stages.vision.AsyncAnthropic") as mock_cls:
            mock_client = MagicMock()
            mock_client.messages = MagicMock()
            mock_client.messages.create = AsyncMock(
                return_value=_mock_response(json.dumps(REJECTED_RESPONSE))
            )
            mock_cls.return_value = mock_client

            evaluator = VisionEvaluator(settings)
            verdict = await evaluator.evaluate(mock_background, mock_event)

            assert verdict.approved is False
            assert len(verdict.rejection_reasons) == 2


# ---------------------------------------------------------------------------
# Ollama backend tests
# ---------------------------------------------------------------------------

OLLAMA_BASE = "https://test-ollama.example.com"


@pytest.fixture
def ollama_settings() -> Settings:
    return Settings(
        vision_provider="ollama",
        ollama_api_key="test-ollama-key",
        ollama_base_url=OLLAMA_BASE,
        ollama_vision_model="llama3.2-vision",
        vision_max_tokens=1024,
        vision_timeout_seconds=30,
        vision_confidence_threshold=0.6,
    )


def _ollama_chat_response(content: str) -> dict:
    """Build an OpenAI-compatible /v1/chat/completions response."""
    return {
        "id": "chatcmpl-test",
        "object": "chat.completion",
        "choices": [{"index": 0, "message": {"role": "assistant", "content": content}}],
    }


class TestOllamaEvaluate:
    @pytest.mark.asyncio
    async def test_ollama_evaluate_correct_payload(
        self,
        ollama_settings: Settings,
        mock_background: GeneratedBackground,
        mock_event: EventInput,
    ) -> None:
        with respx.mock(base_url=OLLAMA_BASE) as mock_api:
            route = mock_api.post("/v1/chat/completions").mock(
                return_value=httpx.Response(
                    200, json=_ollama_chat_response(json.dumps(APPROVED_RESPONSE))
                )
            )

            evaluator = VisionEvaluator(ollama_settings)
            await evaluator.evaluate(mock_background, mock_event)

            assert route.called
            req_body = json.loads(route.calls[0].request.content)
            assert req_body["model"] == "llama3.2-vision"
            assert req_body["messages"][0]["role"] == "system"
            assert req_body["messages"][0]["content"] == VISION_SYSTEM_PROMPT
            user_msg = req_body["messages"][1]
            assert user_msg["role"] == "user"
            assert user_msg["content"][0]["type"] == "image_url"
            assert user_msg["content"][1]["type"] == "text"

    @pytest.mark.asyncio
    async def test_ollama_evaluate_success(
        self,
        ollama_settings: Settings,
        mock_background: GeneratedBackground,
        mock_event: EventInput,
    ) -> None:
        with respx.mock(base_url=OLLAMA_BASE) as mock_api:
            mock_api.post("/v1/chat/completions").mock(
                return_value=httpx.Response(
                    200, json=_ollama_chat_response(json.dumps(APPROVED_RESPONSE))
                )
            )

            evaluator = VisionEvaluator(ollama_settings)
            verdict = await evaluator.evaluate(mock_background, mock_event)

            assert isinstance(verdict, VisionVerdict)
            assert verdict.approved is True
            assert verdict.confidence == 0.85

    @pytest.mark.asyncio
    async def test_ollama_evaluate_retry_on_parse_failure(
        self,
        ollama_settings: Settings,
        mock_background: GeneratedBackground,
        mock_event: EventInput,
    ) -> None:
        with respx.mock(base_url=OLLAMA_BASE) as mock_api:
            route = mock_api.post("/v1/chat/completions").mock(
                side_effect=[
                    httpx.Response(
                        200,
                        json=_ollama_chat_response("Not JSON at all, sorry!"),
                    ),
                    httpx.Response(
                        200,
                        json=_ollama_chat_response(json.dumps(APPROVED_RESPONSE)),
                    ),
                ]
            )

            evaluator = VisionEvaluator(ollama_settings)
            verdict = await evaluator.evaluate(mock_background, mock_event)

            assert isinstance(verdict, VisionVerdict)
            assert verdict.approved is True
            assert route.call_count == 2
            # Verify retry includes conversation history
            retry_body = json.loads(route.calls[1].request.content)
            assert len(retry_body["messages"]) == 4  # system + user + assistant + retry user
            assert retry_body["messages"][-1]["content"] == "Return valid JSON only, no prose."

    @pytest.mark.asyncio
    async def test_ollama_evaluate_raises_on_http_error(
        self,
        ollama_settings: Settings,
        mock_background: GeneratedBackground,
        mock_event: EventInput,
    ) -> None:
        with respx.mock(base_url=OLLAMA_BASE) as mock_api:
            mock_api.post("/v1/chat/completions").mock(
                return_value=httpx.Response(500, text="Internal Server Error")
            )

            evaluator = VisionEvaluator(ollama_settings)
            with pytest.raises(VisionAPIError, match="Ollama API error 500"):
                await evaluator.evaluate(mock_background, mock_event)

    @pytest.mark.asyncio
    async def test_ollama_evaluate_auth_header(
        self,
        ollama_settings: Settings,
        mock_background: GeneratedBackground,
        mock_event: EventInput,
    ) -> None:
        with respx.mock(base_url=OLLAMA_BASE) as mock_api:
            route = mock_api.post("/v1/chat/completions").mock(
                return_value=httpx.Response(
                    200, json=_ollama_chat_response(json.dumps(APPROVED_RESPONSE))
                )
            )

            evaluator = VisionEvaluator(ollama_settings)
            await evaluator.evaluate(mock_background, mock_event)

            auth_header = route.calls[0].request.headers.get("authorization")
            assert auth_header == "Bearer test-ollama-key"

    @pytest.mark.asyncio
    async def test_ollama_evaluate_unexpected_response_format(
        self,
        ollama_settings: Settings,
        mock_background: GeneratedBackground,
        mock_event: EventInput,
    ) -> None:
        with respx.mock(base_url=OLLAMA_BASE) as mock_api:
            mock_api.post("/v1/chat/completions").mock(
                return_value=httpx.Response(200, json={"unexpected": "format"})
            )

            evaluator = VisionEvaluator(ollama_settings)
            with pytest.raises(VisionAPIError, match="Unexpected Ollama response"):
                await evaluator.evaluate(mock_background, mock_event)
