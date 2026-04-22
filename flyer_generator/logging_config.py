"""Structured logging configuration via structlog."""

import structlog

# Conditional import so logging still loads during partial-install bootstrap
# (e.g. during `uv sync` before `asgi-correlation-id` is resolved).
try:
    from asgi_correlation_id import correlation_id as _correlation_id_ctx
except ImportError:  # pragma: no cover - dev bootstrap only
    _correlation_id_ctx = None


def _add_correlation(
    logger: object, method_name: str, event_dict: dict
) -> dict:
    """Stamp ``trace_id`` from the asgi-correlation-id ContextVar if present.

    Belt-and-suspenders to ``structlog.contextvars.merge_contextvars`` — the
    contextvar is already merged into the event dict automatically, but this
    helper normalizes the key name to ``trace_id`` across all log lines
    regardless of how the contextvar was named by middleware.
    """
    if _correlation_id_ctx is None:
        return event_dict
    cid = _correlation_id_ctx.get()
    if cid and "trace_id" not in event_dict:
        event_dict["trace_id"] = cid
    return event_dict


def configure_logging(log_format: str = "text", log_level: str = "INFO") -> None:
    """Configure structlog for the application.

    Args:
        log_format: "json" for production, "text" for development.
        log_level: Standard log level name (DEBUG, INFO, WARNING, ERROR).
    """
    shared_processors: list[structlog.types.Processor] = [
        structlog.contextvars.merge_contextvars,
        _add_correlation,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
    ]

    if log_format == "json":
        shared_processors.append(structlog.processors.JSONRenderer())
    else:
        shared_processors.append(structlog.dev.ConsoleRenderer())

    structlog.configure(
        processors=shared_processors,
        wrapper_class=structlog.make_filtering_bound_logger(
            getattr(structlog, log_level.upper(), 20)
        ),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )


def get_logger() -> structlog.stdlib.BoundLogger:
    """Get a bound logger instance."""
    return structlog.get_logger()
