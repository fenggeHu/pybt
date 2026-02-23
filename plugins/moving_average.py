from __future__ import annotations

from typing import Any, Mapping

from pybt.strategies import MovingAverageCrossStrategy

from pybt.configuration.plugin_helpers import require_str, to_bool


def create(params: Mapping[str, Any], ctx: Mapping[str, Any]) -> MovingAverageCrossStrategy:
    return MovingAverageCrossStrategy(
        symbol=require_str(params, "symbol"),
        short_window=int(params.get("short_window", 5)),
        long_window=int(params.get("long_window", 20)),
        strategy_id=str(params.get("strategy_id", "mac")),
        debug_signal=to_bool(params.get("debug_signal"), default=False),
    )
