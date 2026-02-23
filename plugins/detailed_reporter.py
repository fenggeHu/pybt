from __future__ import annotations

from typing import Any, Mapping

from pybt.analytics import DetailedReporter


def create(params: Mapping[str, Any], ctx: Mapping[str, Any]) -> DetailedReporter:
    return DetailedReporter(
        initial_cash=float(params.get("initial_cash", 100_000.0)),
        track_equity_curve=bool(params.get("track_equity_curve", True)),
    )
