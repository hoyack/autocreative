"""Typed exception hierarchy for the flyer generator."""


class FlyerGeneratorError(Exception):
    """Base exception for all flyer generator errors."""

    def __init__(self, message: str, *, trace_id: str = "", **context: object) -> None:
        self.trace_id = trace_id
        self.context = context
        super().__init__(message)


class ConfigurationError(FlyerGeneratorError):
    """Bad settings or missing API key."""


class InputValidationError(FlyerGeneratorError):
    """Malformed EventInput."""


class UnknownPresetError(FlyerGeneratorError):
    """Requested preset not found in registry."""


class ComfyError(FlyerGeneratorError):
    """Base for all ComfyCloud errors."""


class ComfySubmitError(ComfyError):
    """4xx/5xx on workflow submit."""


class ComfyJobFailedError(ComfyError):
    """Job returned status=failed or cancelled."""


class ComfyJobTimeoutError(ComfyError):
    """Poll max attempts exceeded."""

    def __init__(
        self, message: str, *, prompt_id: str = "", attempts: int = 0, **kwargs: object
    ) -> None:
        super().__init__(message, **kwargs)
        self.prompt_id = prompt_id
        self.attempts = attempts


class ComfyDownloadError(ComfyError):
    """History/view endpoint issues."""


class VisionError(FlyerGeneratorError):
    """Base for vision evaluation errors."""


class VisionResponseParseError(VisionError):
    """JSON response unsalvageable after retry."""


class LLMAPIError(FlyerGeneratorError):
    """Base class for all LLM HTTP errors (Ollama, Anthropic, future providers).

    Subclasses signal retryability semantics; see `stages.llm_retry` for the
    classification rules. Carries optional `model` (which model in the chain
    failed) and `status_code` (HTTP status when applicable).
    """

    def __init__(
        self,
        message: str,
        *,
        model: str | None = None,
        status_code: int | None = None,
        **kwargs: object,
    ) -> None:
        super().__init__(message, **kwargs)
        self.model = model
        self.status_code = status_code


class LLMRateLimitError(LLMAPIError):
    """HTTP 429. Carries retry_after_seconds parsed from the Retry-After header."""

    def __init__(
        self,
        message: str,
        *,
        retry_after_seconds: float | None = None,
        **kwargs: object,
    ) -> None:
        super().__init__(message, **kwargs)
        self.retry_after_seconds = retry_after_seconds


class LLMServiceUnavailableError(LLMAPIError):
    """HTTP 502 / 503 / 500. Retryable against the same model."""


class LLMTimeoutError(LLMAPIError):
    """httpx.ReadTimeout / ConnectTimeout / ConnectError / ReadError. Retryable."""


class LLMModelUnavailableError(LLMAPIError):
    """HTTP 404 or body indicating the requested model is not loaded / not found.

    NOT retryable against the same model — the chain should advance to the next
    fallback model.
    """


class CompositionError(FlyerGeneratorError):
    """SVG build failure."""


class RasterizationError(FlyerGeneratorError):
    """SVG to PNG rasterization failure."""


class MaxAttemptsExceededError(FlyerGeneratorError):
    """Regeneration budget exhausted."""


class BrandKitError(FlyerGeneratorError):
    """Base for all brand-kit errors."""


class BrandKitScrapeError(BrandKitError):
    """Scraper exhausted both Playwright and BS4 paths without usable data."""


class BrandKitContrastError(BrandKitError):
    """Contrast remediation exhausted options with no passing swap."""


class BrandKitAuditError(BrandKitError):
    """Audit loop hit max cycles without clean pass (only raised in strict mode)."""

    def __init__(
        self,
        message: str,
        *,
        cycles: int = 0,
        remaining_issues: list[object] | None = None,
        **kwargs: object,
    ) -> None:
        super().__init__(message, **kwargs)
        self.cycles = cycles
        self.remaining_issues = remaining_issues or []


class BrandVoiceViolationError(BrandKitError):
    """LLM copy contained banned-word or voice violation after retries exhausted."""

    def __init__(
        self,
        message: str,
        *,
        banned_matches: list[str] | None = None,
        keys: list[str] | None = None,
        **kwargs: object,
    ) -> None:
        super().__init__(message, **kwargs)
        self.banned_matches = banned_matches or []
        self.keys = keys or []


# --- Backwards-compatible alias (DEPRECATED) ---
# VisionAPIError was the original name for Anthropic/Ollama API failures.
# New code should catch LLMAPIError (or a specific subclass). Existing
# `except VisionAPIError` sites continue to work because this is a direct
# reference to the same class.
VisionAPIError = LLMAPIError


class SocialError(FlyerGeneratorError):
    """Base for all social-posting errors."""


class PostValidationError(SocialError):
    """Hard platform-validation failure (e.g. body over hard cap)."""

    def __init__(
        self,
        message: str,
        *,
        platform: str | None = None,
        issues: list[object] | None = None,
        **kwargs: object,
    ) -> None:
        super().__init__(message, **kwargs)
        self.platform = platform
        self.issues = issues or []


class PlatformUnsupportedError(SocialError):
    """Unknown platform string passed to generator/campaign."""


class IntentUnsupportedError(SocialError):
    """Unknown intent string."""


class CampaignError(SocialError):
    """Campaign-level orchestration failure."""
