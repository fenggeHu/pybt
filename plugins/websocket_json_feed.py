from __future__ import annotations

from typing import Any, Mapping

from pybt.data import WebSocketJSONFeed

from pybt.configuration.plugin_helpers import require_str


def create(params: Mapping[str, Any], ctx: Mapping[str, Any]) -> WebSocketJSONFeed:
    return WebSocketJSONFeed(
        symbol=require_str(params, "symbol"),
        url=require_str(params, "url"),
        max_ticks=params.get("max_ticks"),
        max_reconnects=int(params.get("max_reconnects", 3)),
        backoff_seconds=float(params.get("backoff_seconds", 0.5)),
        heartbeat_interval=params.get("heartbeat_interval"),
    )
