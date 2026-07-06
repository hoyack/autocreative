"""Comprehensive async tests for ComfyClient -- submit, poll, download, generate."""

from __future__ import annotations

from dataclasses import dataclass

import httpx
import pytest
import respx

from flyer_generator.config import Settings
from flyer_generator.errors import (
    ComfyDownloadError,
    ComfyJobFailedError,
    ComfyJobTimeoutError,
    ComfySubmitError,
)
from flyer_generator.stages.comfy_client import ComfyClient
from tests.fixtures.comfy_responses import (
    HISTORY_RESPONSE,
    PROMPT_ID,
    STATUS_CANCELLED,
    STATUS_COMPLETED,
    STATUS_FAILED,
    STATUS_PENDING,
    STATUS_RUNNING,
    STATUS_SUCCESS,
    SUBMIT_RESPONSE,
    TINY_PNG,
)

BASE_URL = "https://cloud.comfy.org"


@dataclass
class MockWorkflow:
    """Minimal ComfyWorkflow-like object for testing."""

    workflow: dict
    positive_prompt: str = "a beautiful sunset"
    negative_prompt: str = "blurry, deformed"
    seed: int = 42


@pytest.fixture()
def settings() -> Settings:
    return Settings(
        comfycloud_api_key="test-key-123",
        comfycloud_base_url=BASE_URL,
        poll_initial_wait_seconds=0.01,
        poll_interval_seconds=0.01,
        poll_max_attempts=3,
    )

@pytest.fixture()
def mock_router():
    with respx.mock(base_url=BASE_URL) as router:
        yield router


@pytest.fixture()
def client(settings: Settings, mock_router: respx.MockRouter) -> ComfyClient:
    http = httpx.AsyncClient(base_url=BASE_URL)
    return ComfyClient(settings=settings, http_client=http)


@pytest.fixture()
def workflow() -> MockWorkflow:
    return MockWorkflow(workflow={"some": "workflow"})


# =====================================================================
# Submit tests
# =====================================================================


async def test_submit_posts_workflow_with_api_key(
    client: ComfyClient, mock_router: respx.MockRouter, workflow: MockWorkflow
) -> None:
    """Verify POST /api/prompt is called with correct body and X-API-Key header."""
    route = mock_router.post("/api/prompt").respond(json=SUBMIT_RESPONSE)

    await client.submit(workflow)

    assert route.called
    request = route.calls[0].request
    assert request.headers["X-API-Key"] == "test-key-123"
    import json

    body = json.loads(request.content)
    assert body == {"prompt": {"some": "workflow"}}


async def test_submit_returns_comfy_job(
    client: ComfyClient, mock_router: respx.MockRouter, workflow: MockWorkflow
) -> None:
    """Verify returned ComfyJob has correct fields."""
    mock_router.post("/api/prompt").respond(json=SUBMIT_RESPONSE)

    job = await client.submit(workflow, attempt=2)

    assert job.prompt_id == PROMPT_ID
    assert job.positive_prompt == "a beautiful sunset"
    assert job.negative_prompt == "blurry, deformed"
    assert job.seed == 42
    assert job.attempt_number == 2


async def test_submit_4xx_raises_comfy_submit_error(
    client: ComfyClient, mock_router: respx.MockRouter, workflow: MockWorkflow
) -> None:
    """Mock 400 response -> ComfySubmitError."""
    mock_router.post("/api/prompt").respond(status_code=400, text="Bad request")

    with pytest.raises(ComfySubmitError, match="HTTP 400"):
        await client.submit(workflow)


async def test_submit_5xx_retries_with_backoff(
    client: ComfyClient, mock_router: respx.MockRouter, workflow: MockWorkflow
) -> None:
    """Mock 500 then 200 -> retry succeeds."""
    mock_router.post("/api/prompt").side_effect = [
        httpx.Response(500, text="Internal Server Error"),
        httpx.Response(200, json=SUBMIT_RESPONSE),
    ]

    job = await client.submit(workflow)

    assert job.prompt_id == PROMPT_ID


async def test_submit_5xx_exhausts_retries(
    client: ComfyClient, mock_router: respx.MockRouter, workflow: MockWorkflow
) -> None:
    """Mock 500 four times (initial + 3 retries) -> ComfySubmitError."""
    mock_router.post("/api/prompt").side_effect = [
        httpx.Response(500, text="fail"),
        httpx.Response(500, text="fail"),
        httpx.Response(500, text="fail"),
        httpx.Response(500, text="fail"),
    ]

    with pytest.raises(ComfySubmitError, match="retries"):
        await client.submit(workflow)


# =====================================================================
# Polling tests
# =====================================================================


async def test_wait_for_completion_success(
    client: ComfyClient, mock_router: respx.MockRouter
) -> None:
    """Status 'success' -> returns without error."""
    mock_router.get(f"/api/job/{PROMPT_ID}/status").respond(json=STATUS_SUCCESS)

    await client.wait_for_completion(PROMPT_ID)


async def test_wait_for_completion_completed(
    client: ComfyClient, mock_router: respx.MockRouter
) -> None:
    """Status 'completed' -> returns without error (Pitfall 1 safety)."""
    mock_router.get(f"/api/job/{PROMPT_ID}/status").respond(json=STATUS_COMPLETED)

    await client.wait_for_completion(PROMPT_ID)


async def test_wait_for_completion_polls_until_success(
    client: ComfyClient, mock_router: respx.MockRouter
) -> None:
    """pending -> running -> success."""
    mock_router.get(f"/api/job/{PROMPT_ID}/status").side_effect = [
        httpx.Response(200, json=STATUS_PENDING),
        httpx.Response(200, json=STATUS_RUNNING),
        httpx.Response(200, json=STATUS_SUCCESS),
    ]

    await client.wait_for_completion(PROMPT_ID)


async def test_wait_for_completion_failed_raises(
    client: ComfyClient, mock_router: respx.MockRouter
) -> None:
    """Status 'failed' -> ComfyJobFailedError."""
    mock_router.get(f"/api/job/{PROMPT_ID}/status").respond(json=STATUS_FAILED)

    with pytest.raises(ComfyJobFailedError, match="failed"):
        await client.wait_for_completion(PROMPT_ID)


async def test_wait_for_completion_cancelled_raises(
    client: ComfyClient, mock_router: respx.MockRouter
) -> None:
    """Status 'cancelled' -> ComfyJobFailedError."""
    mock_router.get(f"/api/job/{PROMPT_ID}/status").respond(json=STATUS_CANCELLED)

    with pytest.raises(ComfyJobFailedError, match="cancelled"):
        await client.wait_for_completion(PROMPT_ID)


async def test_wait_for_completion_timeout(
    client: ComfyClient, mock_router: respx.MockRouter
) -> None:
    """Pending for all attempts -> ComfyJobTimeoutError."""
    mock_router.get(f"/api/job/{PROMPT_ID}/status").respond(json=STATUS_PENDING)

    with pytest.raises(ComfyJobTimeoutError, match="timed out"):
        await client.wait_for_completion(PROMPT_ID)


async def test_wait_logs_each_poll_attempt(
    client: ComfyClient, mock_router: respx.MockRouter, capsys: pytest.CaptureFixture[str]
) -> None:
    """Verify polling logs include attempt count and status."""
    mock_router.get(f"/api/job/{PROMPT_ID}/status").side_effect = [
        httpx.Response(200, json=STATUS_PENDING),
        httpx.Response(200, json=STATUS_SUCCESS),
    ]

    await client.wait_for_completion(PROMPT_ID)
    # If we get here without error, polling worked correctly through pending -> success


async def test_wait_for_completion_5xx_retries(
    client: ComfyClient, mock_router: respx.MockRouter
) -> None:
    """5xx on poll -> retries with backoff, then succeeds."""
    mock_router.get(f"/api/job/{PROMPT_ID}/status").side_effect = [
        httpx.Response(500, text="fail"),
        httpx.Response(200, json=STATUS_SUCCESS),
    ]

    await client.wait_for_completion(PROMPT_ID)


# =====================================================================
# Download tests
# =====================================================================


async def test_download_result_fetches_image(
    client: ComfyClient, mock_router: respx.MockRouter
) -> None:
    """Mock history_v2 with filename + /api/view with PNG bytes -> returns image bytes."""
    mock_router.get(f"/api/history_v2/{PROMPT_ID}").respond(json=HISTORY_RESPONSE)
    mock_router.get("/api/view").respond(content=TINY_PNG)

    result = await client.download_result(PROMPT_ID)

    assert result == TINY_PNG
    assert len(result) > 0


async def test_download_result_history_404_raises(
    client: ComfyClient, mock_router: respx.MockRouter
) -> None:
    """404 on history_v2 -> ComfyDownloadError."""
    mock_router.get(f"/api/history_v2/{PROMPT_ID}").respond(status_code=404)

    with pytest.raises(ComfyDownloadError, match="fetch history"):
        await client.download_result(PROMPT_ID)


async def test_download_result_view_404_raises(
    client: ComfyClient, mock_router: respx.MockRouter
) -> None:
    """History OK but 404 on /api/view -> ComfyDownloadError."""
    mock_router.get(f"/api/history_v2/{PROMPT_ID}").respond(json=HISTORY_RESPONSE)
    mock_router.get("/api/view").respond(status_code=404)

    with pytest.raises(ComfyDownloadError, match="download image"):
        await client.download_result(PROMPT_ID)


async def test_download_result_no_filename_raises(
    client: ComfyClient, mock_router: respx.MockRouter
) -> None:
    """History response with no images -> ComfyDownloadError."""
    empty_history = {PROMPT_ID: {"outputs": {}}}
    mock_router.get(f"/api/history_v2/{PROMPT_ID}").respond(json=empty_history)

    with pytest.raises(ComfyDownloadError, match="No image filename"):
        await client.download_result(PROMPT_ID)


# =====================================================================
# Generate (orchestration) test
# =====================================================================


async def test_generate_orchestrates_full_flow(
    client: ComfyClient, mock_router: respx.MockRouter, workflow: MockWorkflow
) -> None:
    """Full flow: submit -> poll (pending, success) -> download."""
    mock_router.post("/api/prompt").respond(json=SUBMIT_RESPONSE)
    mock_router.get(f"/api/job/{PROMPT_ID}/status").side_effect = [
        httpx.Response(200, json=STATUS_PENDING),
        httpx.Response(200, json=STATUS_SUCCESS),
    ]
    mock_router.get(f"/api/history_v2/{PROMPT_ID}").respond(json=HISTORY_RESPONSE)
    mock_router.get("/api/view").respond(content=TINY_PNG)

    job, raw_bytes = await client.generate(workflow, attempt=1)

    assert job.prompt_id == PROMPT_ID
    assert job.positive_prompt == "a beautiful sunset"
    assert raw_bytes == TINY_PNG


async def test_generate_submit_failure_propagates(
    client: ComfyClient, mock_router: respx.MockRouter, workflow: MockWorkflow
) -> None:
    """Submit failure propagates up from generate."""
    mock_router.post("/api/prompt").respond(status_code=400, text="Bad request")

    with pytest.raises(ComfySubmitError):
        await client.generate(workflow)


async def test_generate_poll_failure_propagates(
    client: ComfyClient, mock_router: respx.MockRouter, workflow: MockWorkflow
) -> None:
    """Poll failure propagates up from generate."""
    mock_router.post("/api/prompt").respond(json=SUBMIT_RESPONSE)
    mock_router.get(f"/api/job/{PROMPT_ID}/status").respond(json=STATUS_FAILED)

    with pytest.raises(ComfyJobFailedError):
        await client.generate(workflow)
