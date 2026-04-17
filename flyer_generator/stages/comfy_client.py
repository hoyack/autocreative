"""ComfyClient -- async HTTP client for ComfyCloud workflow submission, polling, and download."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Protocol

import httpx
import structlog

from flyer_generator.config import Settings
from flyer_generator.errors import (
    ComfyDownloadError,
    ComfyJobFailedError,
    ComfyJobTimeoutError,
    ComfySubmitError,
)
from flyer_generator.models import ComfyJob

if TYPE_CHECKING:
    from flyer_generator.stages.prompt_builder import ComfyWorkflow

logger = structlog.get_logger()

_SUCCESS_STATUSES = frozenset({"success", "completed"})
_FAILURE_STATUSES = frozenset({"failed", "cancelled"})

_BACKOFF_MAX_RETRIES = 3
_BACKOFF_BASE_SECONDS = 1.0


class ComfyWorkflowLike(Protocol):
    """Structural typing for ComfyWorkflow to avoid hard import dependency."""

    workflow: dict
    positive_prompt: str
    negative_prompt: str
    seed: int


class ComfyClient:
    """Async client for ComfyCloud: submit, poll, download."""

    def __init__(self, settings: Settings, http_client: httpx.AsyncClient) -> None:
        self._settings = settings
        self._http = http_client
        self._base_url = settings.comfycloud_base_url.rstrip("/")
        self._headers = {"X-API-Key": settings.comfycloud_api_key.get_secret_value()}

    # ------------------------------------------------------------------
    # Submit
    # ------------------------------------------------------------------

    async def submit(
        self, workflow: ComfyWorkflow | ComfyWorkflowLike, attempt: int = 1
    ) -> ComfyJob:
        """POST workflow JSON to /api/prompt and return a ComfyJob.

        Retries on 5xx with exponential backoff (3 retries, 1s base).
        Raises ComfySubmitError on 4xx or exhausted retries.
        """
        url = f"{self._base_url}/api/prompt"
        body = {"prompt": workflow.workflow}
        last_resp: httpx.Response | None = None

        for retry in range(_BACKOFF_MAX_RETRIES + 1):
            resp = await self._http.post(url, json=body, headers=self._headers)
            last_resp = resp

            if resp.status_code >= 500:
                if retry < _BACKOFF_MAX_RETRIES:
                    delay = _BACKOFF_BASE_SECONDS * (2**retry)
                    logger.warning(
                        "comfy_submit_retry",
                        status=resp.status_code,
                        retry=retry + 1,
                        delay=delay,
                    )
                    await asyncio.sleep(delay)
                    continue
                # Exhausted retries on 5xx
                raise ComfySubmitError(
                    f"ComfyCloud submit failed after {_BACKOFF_MAX_RETRIES} retries: "
                    f"HTTP {resp.status_code}",
                )

            if resp.status_code >= 400:
                raise ComfySubmitError(
                    f"ComfyCloud submit failed: HTTP {resp.status_code} — {resp.text}",
                )

            # Success
            data = resp.json()
            prompt_id: str = data["prompt_id"]
            logger.info("comfy_submitted", prompt_id=prompt_id)
            return ComfyJob(
                prompt_id=prompt_id,
                submitted_at=datetime.now(timezone.utc),
                positive_prompt=workflow.positive_prompt,
                negative_prompt=workflow.negative_prompt,
                seed=workflow.seed,
                attempt_number=attempt,
            )

        # Should be unreachable, but satisfy type checker
        assert last_resp is not None  # noqa: S101
        raise ComfySubmitError(f"ComfyCloud submit failed: HTTP {last_resp.status_code}")

    # ------------------------------------------------------------------
    # Poll
    # ------------------------------------------------------------------

    async def wait_for_completion(self, prompt_id: str) -> None:
        """Poll /api/job/{id}/status until terminal state.

        Recognizes 'success' and 'completed' as terminal success states.
        Raises ComfyJobFailedError on 'failed'/'cancelled'.
        Raises ComfyJobTimeoutError after max attempts.
        """
        await asyncio.sleep(self._settings.poll_initial_wait_seconds)
        start = asyncio.get_event_loop().time()

        for attempt in range(1, self._settings.poll_max_attempts + 1):
            elapsed = asyncio.get_event_loop().time() - start
            resp = await self._request_with_backoff(
                "GET",
                f"{self._base_url}/api/job/{prompt_id}/status",
            )
            status = resp.json().get("status", "unknown")

            logger.info(
                "comfy_poll",
                prompt_id=prompt_id,
                attempt=attempt,
                elapsed_s=round(elapsed, 1),
                status=status,
            )

            if status in _SUCCESS_STATUSES:
                return
            if status in _FAILURE_STATUSES:
                raise ComfyJobFailedError(
                    f"ComfyCloud job {status}: {prompt_id}",
                    prompt_id=prompt_id,
                )
            await asyncio.sleep(self._settings.poll_interval_seconds)

        max_attempts = self._settings.poll_max_attempts
        raise ComfyJobTimeoutError(
            f"ComfyCloud job timed out after {max_attempts} polls",
            prompt_id=prompt_id,
            attempts=max_attempts,
        )

    # ------------------------------------------------------------------
    # Download
    # ------------------------------------------------------------------

    async def download_result(self, prompt_id: str) -> bytes:
        """Fetch the generated image via history_v2 + /api/view.

        Raises ComfyDownloadError on any failure.
        """
        # Step 1: Get output filename from history
        history_url = f"{self._base_url}/api/history_v2/{prompt_id}"
        resp = await self._http.get(history_url, headers=self._headers)
        if resp.status_code != 200:
            raise ComfyDownloadError(
                f"Failed to fetch history for {prompt_id}: HTTP {resp.status_code}",
            )

        filename = self._extract_filename(resp.json(), prompt_id)

        # Step 2: Download image via /api/view
        view_url = f"{self._base_url}/api/view"
        resp = await self._http.get(
            view_url,
            params={"filename": filename},
            headers=self._headers,
        )
        if resp.status_code != 200:
            raise ComfyDownloadError(
                f"Failed to download image {filename}: HTTP {resp.status_code}",
            )

        content = resp.content
        logger.info("comfy_downloaded", prompt_id=prompt_id, size_bytes=len(content))
        return content

    # ------------------------------------------------------------------
    # Orchestration
    # ------------------------------------------------------------------

    async def generate(
        self, workflow: ComfyWorkflow | ComfyWorkflowLike, attempt: int = 1
    ) -> tuple[ComfyJob, bytes]:
        """Full lifecycle: submit -> wait -> download.

        Returns (ComfyJob, raw_image_bytes).
        """
        job = await self.submit(workflow, attempt)
        await self.wait_for_completion(job.prompt_id)
        raw_bytes = await self.download_result(job.prompt_id)
        logger.info("comfy_generate_complete", prompt_id=job.prompt_id, attempt=attempt)
        return (job, raw_bytes)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _request_with_backoff(self, method: str, url: str) -> httpx.Response:
        """Execute an HTTP request with exponential backoff on 5xx."""
        last_resp: httpx.Response | None = None
        for retry in range(_BACKOFF_MAX_RETRIES + 1):
            resp = await self._http.request(method, url, headers=self._headers)
            last_resp = resp

            if resp.status_code >= 500:
                if retry < _BACKOFF_MAX_RETRIES:
                    delay = _BACKOFF_BASE_SECONDS * (2**retry)
                    logger.warning(
                        "comfy_request_retry",
                        url=url,
                        status=resp.status_code,
                        retry=retry + 1,
                        delay=delay,
                    )
                    await asyncio.sleep(delay)
                    continue
            return resp

        assert last_resp is not None  # noqa: S101
        return last_resp

    @staticmethod
    def _extract_filename(history_data: dict, prompt_id: str) -> str:
        """Walk history_v2 response to find the first image filename."""
        image_extensions = (".png", ".jpg", ".jpeg", ".webp")

        # history_v2 response can be nested under the prompt_id key
        data = history_data.get(prompt_id, history_data)

        # Walk outputs looking for images
        outputs = data.get("outputs", {})
        for _node_id, node_output in outputs.items():
            images = node_output.get("images", [])
            for image_info in images:
                fname = image_info.get("filename", "")
                if fname and any(fname.lower().endswith(ext) for ext in image_extensions):
                    return fname

        raise ComfyDownloadError(
            f"No image filename found in history_v2 response for {prompt_id}",
        )
