"""
Structured logging for the pipeline.

Usage:
    from pipeline.log import get_logger
    log = get_logger(__name__)
    log.info("Processing chunk", extra={"chunk": 3, "lang": "hi-IN"})

Outputs pretty logs for TTY, structured JSON when LOG_FORMAT=json.
"""

import logging
import json
import os
import sys


class _PrettyFormatter(logging.Formatter):
    """Terminal-friendly formatter that preserves the existing print style."""

    ICONS = {
        logging.DEBUG:    "  . ",
        logging.INFO:     "  \u2192 ",
        logging.WARNING:  "  \u26a0 ",
        logging.ERROR:    "  \u2717 ",
        logging.CRITICAL: "  \u2717\u2717 ",
    }

    def format(self, record):
        icon = self.ICONS.get(record.levelno, "  ")
        msg = record.getMessage()
        return f"{icon}{msg}"


class _JsonFormatter(logging.Formatter):
    """Single-line JSON per log record for production / log aggregation."""

    def format(self, record):
        entry = {
            "ts": self.formatTime(record),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        # Merge any extra keys the caller passed
        for key in ("job_id", "chunk", "scene", "lang", "api", "attempt",
                     "duration", "status_code", "path"):
            val = getattr(record, key, None)
            if val is not None:
                entry[key] = val
        if record.exc_info and record.exc_info[0]:
            entry["exception"] = self.formatException(record.exc_info)
        return json.dumps(entry, default=str)


def get_logger(name: str) -> logging.Logger:
    """Return a configured logger. Safe to call multiple times per module."""
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger

    level = os.environ.get("LOG_LEVEL", "INFO").upper()
    logger.setLevel(getattr(logging, level, logging.INFO))

    handler = logging.StreamHandler(sys.stderr)
    fmt = os.environ.get("LOG_FORMAT", "pretty")
    if fmt == "json":
        handler.setFormatter(_JsonFormatter())
    else:
        handler.setFormatter(_PrettyFormatter())

    logger.addHandler(handler)
    logger.propagate = False
    return logger
