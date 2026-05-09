from __future__ import annotations
import json
import logging
import sys
from datetime import datetime, timezone


class _JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        log = {
            "ts":     datetime.now(timezone.utc).isoformat(),
            "level":  record.levelname,
            "logger": record.name,
            "msg":    record.getMessage(),
        }
        if record.exc_info:
            log["exc"] = self.formatException(record.exc_info)
        return json.dumps(log, ensure_ascii=False)


class _ColourFormatter(logging.Formatter):
    _C = {
        "DEBUG":   "\x1b[36m",
        "INFO":    "\x1b[32m",
        "WARNING": "\x1b[33m",
        "ERROR":   "\x1b[31m",
    }
    _R = "\x1b[0m"

    def format(self, record: logging.LogRecord) -> str:
        c  = self._C.get(record.levelname, "")
        ts = datetime.now(timezone.utc).strftime("%H:%M:%S")
        return f"{ts} {c}{record.levelname:<8}{self._R} {record.name} | {record.getMessage()}"


def configure_logging(level: str = "INFO", production: bool = False) -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(_JsonFormatter() if production else _ColourFormatter())
    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(getattr(logging, level.upper(), logging.INFO))
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("anthropic").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)