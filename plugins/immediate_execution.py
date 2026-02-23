from __future__ import annotations

from typing import Any, Mapping

from pybt.execution import ImmediateExecutionHandler


def create(
    params: Mapping[str, Any], ctx: Mapping[str, Any]
) -> ImmediateExecutionHandler:
    return ImmediateExecutionHandler(
        slippage=float(params.get("slippage", 0.0)),
        commission=float(params.get("commission", 0.0)),
        partial_fill_ratio=params.get("partial_fill_ratio"),
        max_staleness=params.get("max_staleness"),
        fill_timing=str(params.get("fill_timing", "current_close")),
    )
