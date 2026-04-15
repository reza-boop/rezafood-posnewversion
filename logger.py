"""Application-wide logging setup for RezaFood POS.

A rotating file handler writes records to *logs/rezafood.log* (up to
:data:`config.LOG_MAX_BYTES` per file, keeping :data:`config.LOG_BACKUP_COUNT`
backups).  When the ``REZAFOOD_LOG_JSON=1`` environment variable is set the
handler emits newline-delimited JSON instead of plain text.

The log level defaults to ``INFO`` in production and ``DEBUG`` when
``REZAFOOD_ENV=development``.

Import the pre-built ``logger`` instance from here everywhere you need logging::

    from logger import logger
    logger.info("Something happened")
    logger.error("Oops", exc_info=True)
"""

from __future__ import annotations

import json
import logging
import logging.handlers
import os

from config import LOG_BACKUP_COUNT, LOG_FILE, LOG_JSON, LOG_LEVEL, LOG_MAX_BYTES


class _JsonFormatter(logging.Formatter):
    """Emit each log record as a single-line JSON object."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict = {
            "time": self.formatTime(record, "%Y-%m-%dT%H:%M:%S"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False)


def _setup() -> logging.Logger:
    log_dir = os.path.dirname(LOG_FILE)
    if log_dir:
        os.makedirs(log_dir, exist_ok=True)

    handler: logging.Handler = logging.handlers.RotatingFileHandler(
        LOG_FILE,
        maxBytes=LOG_MAX_BYTES,
        backupCount=LOG_BACKUP_COUNT,
        encoding="utf-8",
    )

    if LOG_JSON:
        handler.setFormatter(_JsonFormatter())
    else:
        fmt = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
        handler.setFormatter(logging.Formatter(fmt))

    numeric_level = getattr(logging, LOG_LEVEL.upper(), logging.INFO)
    handler.setLevel(logging.DEBUG)  # handler accepts all; root controls level

    root = logging.getLogger()
    if not root.handlers:
        root.addHandler(handler)
        root.setLevel(numeric_level)

    return logging.getLogger("rezafood")


logger: logging.Logger = _setup()
