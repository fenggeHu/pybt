from __future__ import annotations

from typing import Any, Mapping

from pybt.analytics import EquityCurveReporter


def create(params: Mapping[str, Any], ctx: Mapping[str, Any]) -> EquityCurveReporter:
    return EquityCurveReporter(initial_cash=float(params.get("initial_cash", 100_000.0)))
