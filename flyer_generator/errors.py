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


class VisionAPIError(VisionError):
    """4xx/5xx from Anthropic API."""


class VisionResponseParseError(VisionError):
    """JSON response unsalvageable after retry."""


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
