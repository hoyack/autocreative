"""Single exception-handler bank for Phase 20. Registered at app init.

The ``_payload`` helper intentionally serializes ONLY ``{detail, error_type,
trace_id}``. The ``exc.context`` kwargs bag (which may carry filesystem paths,
SSRF reasons, SecretStr values, or other internal state) is deliberately
omitted — see Phase 20 threat register T-3 (Information Disclosure).
"""

from __future__ import annotations

from asgi_correlation_id import correlation_id
from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from flyer_generator.errors import (
    BrandKitError,
    BrandKitNotFoundError,
    BrandVoiceViolationError,
    ComfyError,
    FlyerGeneratorError,
    LLMAPIError,
    LLMRateLimitError,
    SocialError,
)


def _payload(exc: Exception) -> dict:
    """Every error response has this shape."""
    return {
        "detail": str(exc),
        "error_type": type(exc).__name__,
        "trace_id": correlation_id.get() or "",
    }


def register_exception_handlers(app: FastAPI) -> None:
    """Register domain error handlers in most-specific-first order.

    FastAPI matches the FIRST handler whose ``isinstance(exc, X)`` is true;
    ordering is load-bearing.
    """

    @app.exception_handler(LLMRateLimitError)
    async def _rate_limit(request: Request, exc: LLMRateLimitError) -> JSONResponse:
        retry_after = int(getattr(exc, "retry_after_seconds", 1) or 1)
        return JSONResponse(
            _payload(exc), status_code=503, headers={"Retry-After": str(retry_after)}
        )

    @app.exception_handler(LLMAPIError)
    async def _llm_api(request: Request, exc: LLMAPIError) -> JSONResponse:
        # Catches VisionAPIError (alias) + LLMServiceUnavailable / LLMTimeout /
        # LLMModelUnavailable (NOT LLMRateLimitError — matched earlier).
        return JSONResponse(_payload(exc), status_code=502)

    @app.exception_handler(ComfyError)
    async def _comfy(request: Request, exc: ComfyError) -> JSONResponse:
        return JSONResponse(_payload(exc), status_code=502)

    @app.exception_handler(BrandVoiceViolationError)
    async def _voice(request: Request, exc: BrandVoiceViolationError) -> JSONResponse:
        return JSONResponse(_payload(exc), status_code=422)

    @app.exception_handler(BrandKitNotFoundError)
    async def _kit_not_found(
        request: Request, exc: BrandKitNotFoundError
    ) -> JSONResponse:
        return JSONResponse(_payload(exc), status_code=404)

    @app.exception_handler(BrandKitError)
    async def _brand_kit(request: Request, exc: BrandKitError) -> JSONResponse:
        # Default for scrape / contrast / audit errors.
        return JSONResponse(_payload(exc), status_code=400)

    @app.exception_handler(SocialError)
    async def _social(request: Request, exc: SocialError) -> JSONResponse:
        return JSONResponse(_payload(exc), status_code=400)

    @app.exception_handler(FlyerGeneratorError)
    async def _domain_catch_all(
        request: Request, exc: FlyerGeneratorError
    ) -> JSONResponse:
        # ConfigurationError, InputValidationError, UnknownPresetError, and
        # any other uncategorized domain error lands here.
        return JSONResponse(_payload(exc), status_code=400)

    @app.exception_handler(RequestValidationError)
    async def _pydantic_validation(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        # Pydantic body / query / path validation — always 422.
        # jsonable_encoder handles Pydantic v2's ``ctx.error`` ValueError objects
        # that arrive from custom ``@field_validator`` branches (which are NOT
        # natively JSON-serializable).
        return JSONResponse(
            {
                "detail": jsonable_encoder(exc.errors()),
                "error_type": "RequestValidationError",
                "trace_id": correlation_id.get() or "",
            },
            status_code=422,
        )
