"""Tests for flyer_generator.errors — exception hierarchy."""

from flyer_generator.errors import (
    ComfyDownloadError,
    ComfyError,
    ComfyJobFailedError,
    ComfyJobTimeoutError,
    ComfySubmitError,
    CompositionError,
    ConfigurationError,
    FlyerGeneratorError,
    InputValidationError,
    MaxAttemptsExceededError,
    RasterizationError,
    UnknownPresetError,
    VisionAPIError,
    VisionError,
    VisionResponseParseError,
)


class TestErrorHierarchy:
    def test_hierarchy_comfy_errors(self):
        for cls in [ComfySubmitError, ComfyJobFailedError, ComfyJobTimeoutError, ComfyDownloadError]:
            assert issubclass(cls, ComfyError)
            assert issubclass(cls, FlyerGeneratorError)

    def test_hierarchy_vision_errors(self):
        for cls in [VisionAPIError, VisionResponseParseError]:
            assert issubclass(cls, VisionError)
            assert issubclass(cls, FlyerGeneratorError)

    def test_hierarchy_other_errors(self):
        for cls in [
            ConfigurationError,
            InputValidationError,
            UnknownPresetError,
            CompositionError,
            RasterizationError,
            MaxAttemptsExceededError,
        ]:
            assert issubclass(cls, FlyerGeneratorError)

    def test_error_context(self):
        err = FlyerGeneratorError("boom", trace_id="t-123", foo="bar")
        assert err.trace_id == "t-123"
        assert err.context == {"foo": "bar"}
        assert str(err) == "boom"

    def test_comfy_timeout_fields(self):
        err = ComfyJobTimeoutError(
            "timed out", prompt_id="p-456", attempts=20, trace_id="t-789"
        )
        assert err.prompt_id == "p-456"
        assert err.attempts == 20
        assert err.trace_id == "t-789"
