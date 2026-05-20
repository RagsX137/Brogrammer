import logging
import os
import sys
from datetime import datetime, timezone


def setup_logging(name: str = "brogrammer") -> logging.Logger:
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger

    level = os.environ.get("LOG_LEVEL", "INFO").upper()
    log_format = os.environ.get("LOG_FORMAT", "pretty")

    if log_format == "json":
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(_JSONFormatter())
    else:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(logging.Formatter(
            "%(asctime)s [%(levelname)s] %(message)s",
            datefmt="%Y-%m-%dT%H:%M:%S",
        ))

    logger.addHandler(handler)
    logger.setLevel(getattr(logging, level, logging.INFO))
    return logger


class _JSONFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        import json
        return json.dumps({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "event": record.getMessage(),
            "logger": record.name,
        })
