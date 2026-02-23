from __future__ import annotations

from typing import Any, Mapping

from pybt.data import MultiSourceQuoteFeed

from pybt.configuration.plugin_helpers import as_mapping, as_str_mapping, require_str, to_bool

_DEFAULT_FIELD_MAP = {"price": "3", "volume": "8", "amount": "9"}


def create(params: Mapping[str, Any], ctx: Mapping[str, Any]) -> MultiSourceQuoteFeed:
    transport = str(params.get("transport", "api")).strip().lower()
    if transport != "api":
        raise ValueError("sina_marketdata only supports transport=api")

    url = str(params.get("url", "https://hq.sinajs.cn/list={symbol}"))
    source: dict[str, Any] = {
        "type": "api",
        "url": url,
        "response_mode": str(params.get("response_mode", "sina_hq")),
        "symbol_transform": str(params.get("symbol_transform", "cn_prefix")),
    }
    field_map = params.get("field_map")
    if field_map is None:
        source["field_map"] = dict(_DEFAULT_FIELD_MAP)
    elif isinstance(field_map, Mapping):
        source["field_map"] = {str(k): v for k, v in field_map.items()}
    else:
        raise ValueError("params.field_map must be an object")

    headers = as_str_mapping(params.get("headers"), "params.headers")
    if headers:
        source["headers"] = headers
    query = as_mapping(params.get("query"), "params.query")
    if query:
        source["params"] = query

    for key in ("encoding", "symbol_param", "symbol_template", "on_demand_only"):
        if params.get(key) is not None:
            source[key] = params[key]

    return MultiSourceQuoteFeed(
        symbol=require_str(params, "symbol"),
        max_ticks=params.get("max_ticks"),
        max_reconnects=int(params.get("max_reconnects", 3)),
        backoff_seconds=float(params.get("backoff_seconds", 0.5)),
        connect_timeout=float(params.get("connect_timeout", 5.0)),
        read_timeout=float(params.get("read_timeout", 30.0)),
        price_scale=float(params.get("price_scale", 100.0)),
        source_failure_threshold=int(params.get("source_failure_threshold", 2)),
        source_cooldown_seconds=float(params.get("source_cooldown_seconds", 2.0)),
        emit_source_status=to_bool(params.get("emit_source_status"), default=True),
        sources=[source],
    )
