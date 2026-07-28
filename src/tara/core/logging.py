"""Logging configuration for TARA.

Provides a single `configure_logging` entry point so the application
(CLI, API server, or test suite) controls log formatting and level in
one place, and a `get_logger` helper so individual modules don't need
to know about that configuration to obtain a properly named logger.
"""
from __future__ import annotations

import logging
import sys

_CONFIGURED = False

_LOG_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"


def configure_logging(level: str = "INFO") -> None:
    """Configure the root logger for the whole process.

    Idempotent: calling this more than once (e.g. once from the API
    entrypoint and once from a test fixture) will not attach duplicate
    handlers.

    Args:
        level: A standard logging level name, e.g. "DEBUG", "INFO", "WARNING".
    """
    global _CONFIGURED
    if _CONFIGURED:
        return

    handler = logging.StreamHandler(stream=sys.stdout)
    handler.setFormatter(logging.Formatter(_LOG_FORMAT))

    root = logging.getLogger()
    root.setLevel(level.upper())
    root.addHandler(handler)

    _CONFIGURED = True


def get_logger(name: str) -> logging.Logger:
    """Return a module-scoped logger, configuring logging with defaults if needed.

    Args:
        name: Typically `__name__` of the calling module.

    Returns:
        A standard library `Logger` instance.
    """
    if not _CONFIGURED:
        configure_logging()
    return logging.getLogger(name)
