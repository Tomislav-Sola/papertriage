import contextvars
import logging
import sys

import structlog

from papertriage.core.config import settings

_run_id_var: contextvars.ContextVar[str | None] = contextvars.ContextVar("run_id", default=None)


def _add_run_id(logger: object, method: str, event_dict: dict) -> dict:  # noqa: ARG001
    run_id = _run_id_var.get()
    if run_id is not None:
        event_dict["run_id"] = run_id
    return event_dict


def configure_logging() -> None:
    shared_processors: list = [
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso"),
        _add_run_id,
        structlog.processors.StackInfoRenderer(),
    ]

    if settings.env == "dev":
        renderer = structlog.dev.ConsoleRenderer()
    else:
        renderer = structlog.processors.JSONRenderer()

    structlog.configure(
        processors=shared_processors + [structlog.stdlib.ProcessorFormatter.wrap_for_formatter],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    formatter = structlog.stdlib.ProcessorFormatter(
        processors=[structlog.stdlib.ProcessorFormatter.remove_processors_meta, renderer],
        foreign_pre_chain=shared_processors,
    )

    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(formatter)

    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(settings.log_level.upper())


configure_logging()


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    return structlog.get_logger(name)


def set_run_id(run_id: str) -> contextvars.Token:
    return _run_id_var.set(run_id)


def reset_run_id(token: contextvars.Token) -> None:
    _run_id_var.reset(token)
