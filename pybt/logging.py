"""Logging helpers for PyBT.

Usage:
    from pybt import configure_logging
    configure_logging(level="INFO")

Keeps setup lightweight; callers can further customize the root logger if needed.
"""

import json
import logging
from dataclasses import asdict, is_dataclass
from typing import Optional

from pybt.core.events import Event


class _JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:  # type: ignore[override]
        payload = {
            "ts": self.formatTime(record, "%Y-%m-%dT%H:%M:%S"),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        return json.dumps(payload, ensure_ascii=False)


def configure_logging(level: str = "INFO", fmt: Optional[str] = None, json_format: bool = False) -> None:
    """Configure basic logging for applications using PyBT.

    Parameters
    ----------
    level: str
        Logging level name, e.g. "DEBUG"/"INFO"/"WARNING".
    fmt: Optional[str]
        Optional log format string. Defaults to a concise human-friendly format.
        Ignored when ``json_format`` is True.
    json_format: bool
        Emit logs as JSON lines with fields ts/level/logger/msg.
    """

    if json_format:
        handler = logging.StreamHandler()
        handler.setFormatter(_JsonFormatter())
        logging.basicConfig(level=getattr(logging, level.upper(), logging.INFO), handlers=[handler])
    else:
        if fmt is None:
            fmt = "%(asctime)s %(levelname)s %(name)s - %(message)s"
        logging.basicConfig(level=getattr(logging, level.upper(), logging.INFO), format=fmt)


def log_event(logger: logging.Logger, event: Event, level: str = "INFO", **extra: object) -> None:
    payload = {
        "event_type": event.__class__.__name__,
        "timestamp": getattr(event, "timestamp", None),
    }
    if hasattr(event, "symbol"):
        payload["symbol"] = getattr(event, "symbol")
    if hasattr(event, "strategy_id"):
        payload["strategy_id"] = getattr(event, "strategy_id")
    if is_dataclass(event):
        payload.update(asdict(event))
    logger.log(getattr(logging, level.upper(), logging.INFO), "event", extra={"event": payload, **extra})


__all__ = ["configure_logging", "log_event"]
