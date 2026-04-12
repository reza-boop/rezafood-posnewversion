"""Application-wide logging setup for RezaFood POS.

A file handler writes INFO+ records to *logs/rezafood.log*.
Import the pre-built ``logger`` instance from here everywhere you need logging.

Usage::

    from logger import logger
    logger.info("Something happened")
    logger.error("Oops", exc_info=True)
"""

from __future__ import annotations

import logging
import os

from config import LOG_FILE


def _setup() -> logging.Logger:
    log_dir = os.path.dirname(LOG_FILE)
    if log_dir:
        os.makedirs(log_dir, exist_ok=True)

    fmt = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    file_handler = logging.FileHandler(LOG_FILE, encoding="utf-8")
    file_handler.setFormatter(logging.Formatter(fmt))
    file_handler.setLevel(logging.DEBUG)

    root = logging.getLogger()
    if not root.handlers:
        root.addHandler(file_handler)
        root.setLevel(logging.INFO)

    return logging.getLogger("rezafood")


logger: logging.Logger = _setup()
