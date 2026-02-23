from __future__ import annotations

from typing import Any, Mapping

from pybt.strategies import UptrendBreakoutStrategy

from pybt.configuration.plugin_helpers import require_str, to_bool


def create(params: Mapping[str, Any], ctx: Mapping[str, Any]) -> UptrendBreakoutStrategy:
    return UptrendBreakoutStrategy(
        symbol=require_str(params, "symbol"),
        window=int(params.get("window", 20)),
        breakout_factor=float(params.get("breakout_factor", 1.5)),
        strategy_id=str(params.get("strategy_id", "uptrend")),
        debug_signal=to_bool(params.get("debug_signal"), default=False),
    )
