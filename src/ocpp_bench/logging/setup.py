from __future__ import annotations

import logging
import sys
from typing import Any

import structlog
from structlog.contextvars import bind_contextvars, clear_contextvars, unbind_contextvars

_state: dict[str, bool] = {"configured": False}


def configure(level: str = "info", json_output: bool = True) -> None:
    numeric = getattr(logging, level.upper(), logging.INFO)
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stderr,
        level=numeric,
        force=True,
    )

    renderer: Any = (
        structlog.processors.JSONRenderer()
        if json_output
        else structlog.dev.ConsoleRenderer(colors=sys.stderr.isatty())
    )
    processors: list[Any] = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        renderer,
    ]
    structlog.configure(
        processors=processors,
        wrapper_class=structlog.make_filtering_bound_logger(numeric),
        logger_factory=structlog.PrintLoggerFactory(file=sys.stderr),
        cache_logger_on_first_use=True,
    )
    _state["configured"] = True


def get_logger(name: str | None = None) -> structlog.stdlib.BoundLogger:
    if not _state["configured"]:
        configure()
    logger: structlog.stdlib.BoundLogger = (
        structlog.get_logger(name) if name else structlog.get_logger()
    )
    return logger


def bind_station(charge_point_id: str, **extra: Any) -> None:
    bind_contextvars(charge_point_id=charge_point_id, **extra)


def unbind_station() -> None:
    # Scoped unbind so other logs in the task don't lose unrelated context.
    unbind_contextvars("charge_point_id")


def clear() -> None:
    clear_contextvars()
