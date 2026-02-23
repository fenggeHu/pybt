from __future__ import annotations

from typing import Any, Mapping

from pybt.data import ADataLiveFeed

from pybt.configuration.plugin_helpers import require_str


def create(params: Mapping[str, Any], ctx: Mapping[str, Any]) -> ADataLiveFeed:
    return ADataLiveFeed(
        symbol=require_str(params, "symbol"),
        poll_interval=float(params.get("poll_interval", 1.0)),
        max_ticks=params.get("max_ticks"),
    )
