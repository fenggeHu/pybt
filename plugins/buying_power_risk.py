from __future__ import annotations

from typing import Any, Mapping

from pybt.risk import BuyingPowerRisk


def create(params: Mapping[str, Any], ctx: Mapping[str, Any]) -> BuyingPowerRisk:
    return BuyingPowerRisk(
        initial_cash=float(params.get("initial_cash", 100_000.0)),
        max_leverage=float(params.get("max_leverage", 1.0)),
        reserve_cash=float(params.get("reserve_cash", 0.0)),
    )
