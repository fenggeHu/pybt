from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from pybt.analytics import TradeLogReporter


def create(params: Mapping[str, Any], ctx: Mapping[str, Any]) -> TradeLogReporter:
    jsonl_path = params.get("jsonl_path")
    sqlite_path = params.get("sqlite_path")
    return TradeLogReporter(
        jsonl_path=Path(str(jsonl_path)) if jsonl_path else None,
        sqlite_path=Path(str(sqlite_path)) if sqlite_path else None,
    )
