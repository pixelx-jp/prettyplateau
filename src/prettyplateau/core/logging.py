from __future__ import annotations

import logging

_DEFAULT_FORMAT = "%(asctime)s %(levelname)-7s prettyplateau.%(name)s: %(message)s"


def get_logger(name: str) -> logging.Logger:
    """Return a namespaced logger; configuration is left to the host process."""
    logger = logging.getLogger(f"prettyplateau.{name}")
    if not logger.handlers and not logging.getLogger().handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter(_DEFAULT_FORMAT))
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
    return logger
