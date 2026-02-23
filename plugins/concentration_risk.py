from __future__ import annotations

from typing import Any, Mapping

from pybt.risk import ConcentrationRisk


def create(params: Mapping[str, Any], ctx: Mapping[str, Any]) -> ConcentrationRisk:
    return ConcentrationRisk(
        initial_cash=float(params.get("initial_cash", 100_000.0)),
        max_fraction=float(params.get("max_fraction", 0.5)),
    )
