from __future__ import annotations

from typing import Any, Mapping

from pybt.portfolio import NaivePortfolio


def create(params: Mapping[str, Any], ctx: Mapping[str, Any]) -> NaivePortfolio:
    return NaivePortfolio(
        lot_size=int(params.get("lot_size", 100)),
        initial_cash=float(params.get("initial_cash", 100_000.0)),
    )
