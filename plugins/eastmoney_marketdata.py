from __future__ import annotations

from typing import Any, Mapping

from pybt.data import MultiSourceQuoteFeed

from pybt.configuration.plugin_helpers import as_mapping, as_object_array, as_str_mapping, require_str, to_bool


def _build_transport_source(params: Mapping[str, Any]) -> list[dict[str, Any]]:
    sources = as_object_array(params.get("sources"), "params.sources")
    if sources:
        return sources

    transport = str(params.get("transport", "sse")).strip().lower()
    field_map = params.get("field_map")
    if field_map is not None and not isinstance(field_map, Mapping):
        raise ValueError("params.field_map must be an object")

    if transport == "sse":
        sse_source: dict[str, Any] = {"type": "sse"}
        if params.get("sse_url") is not None:
            sse_source["sse_url"] = str(params["sse_url"])
        if params.get("sse_base_url") is not None:
            sse_source["sse_base_url"] = str(params["sse_base_url"])
        headers = as_str_mapping(params.get("headers"), "params.headers")
        if headers:
            sse_source["headers"] = headers
        if field_map is not None:
            sse_source["field_map"] = dict(field_map)
        if params.get("reconnect_every_ticks") is not None:
            sse_source["reconnect_every_ticks"] = int(params["reconnect_every_ticks"])
        if params.get("heartbeat_timeout") is not None:
            sse_source["heartbeat_timeout"] = float(params["heartbeat_timeout"])

        out = [sse_source]
        if to_bool(params.get("snapshot_fallback"), default=True):
            snapshot_source: dict[str, Any] = {
                "type": "snapshot_api",
                "on_demand_only": True,
            }
            if params.get("snapshot_url") is not None:
                snapshot_source["snapshot_url"] = str(params["snapshot_url"])
            snapshot_headers = as_str_mapping(
                params.get("snapshot_headers"), "params.snapshot_headers"
            )
            if snapshot_headers:
                snapshot_source["headers"] = snapshot_headers
            snapshot_params = as_mapping(
                params.get("snapshot_params"), "params.snapshot_params"
            )
            if snapshot_params:
                snapshot_source["params"] = snapshot_params
            snapshot_field_map = params.get("snapshot_field_map")
            if snapshot_field_map is not None:
                if not isinstance(snapshot_field_map, Mapping):
                    raise ValueError("params.snapshot_field_map must be an object")
                snapshot_source["field_map"] = dict(snapshot_field_map)
            out.append(snapshot_source)
        return out

    if transport == "api":
        url = params.get("url")
        if not isinstance(url, str) or not url:
            raise ValueError("params.url is required when transport=api")
        source = {
            "type": "api",
            "url": url,
            "response_mode": str(params.get("response_mode", "json_or_jsonp")),
        }
        headers = as_str_mapping(params.get("headers"), "params.headers")
        if headers:
            source["headers"] = headers
        extra_params = as_mapping(params.get("query"), "params.query")
        if extra_params:
            source["params"] = extra_params
        if field_map is not None:
            source["field_map"] = dict(field_map)
        for key in (
            "symbol_param",
            "symbol_template",
            "symbol_transform",
            "encoding",
            "on_demand_only",
        ):
            if params.get(key) is not None:
                source[key] = params[key]
        return [source]

    if transport == "websocket":
        url = params.get("url")
        if not isinstance(url, str) or not url:
            raise ValueError("params.url is required when transport=websocket")
        source = {"type": "websocket", "url": url}
        headers = as_str_mapping(params.get("headers"), "params.headers")
        if headers:
            source["headers"] = headers
        if field_map is not None:
            source["field_map"] = dict(field_map)
        if params.get("heartbeat_interval") is not None:
            source["heartbeat_interval"] = float(params["heartbeat_interval"])
        return [source]

    raise ValueError("params.transport must be one of sse/api/websocket")


def create(params: Mapping[str, Any], ctx: Mapping[str, Any]) -> MultiSourceQuoteFeed:
    return MultiSourceQuoteFeed(
        symbol=require_str(params, "symbol"),
        sse_url=(str(params["sse_url"]) if params.get("sse_url") is not None else None),
        secid=(str(params["secid"]) if params.get("secid") is not None else None),
        token=str(params.get("token", "")),
        cname=(str(params["cname"]) if params.get("cname") is not None else None),
        seq=int(params.get("seq", 0)),
        noop=int(params.get("noop", 0)),
        max_ticks=params.get("max_ticks"),
        max_reconnects=int(params.get("max_reconnects", 3)),
        backoff_seconds=float(params.get("backoff_seconds", 0.5)),
        connect_timeout=float(params.get("connect_timeout", 5.0)),
        read_timeout=float(params.get("read_timeout", 30.0)),
        sse_base_url=str(params.get("sse_base_url", "https://92.newspush.eastmoney.com/sse")),
        sse_headers=as_str_mapping(params.get("sse_headers"), "params.sse_headers"),
        snapshot_url=str(
            params.get("snapshot_url", "https://push2.eastmoney.com/api/qt/stock/get")
        ),
        snapshot_fields=str(params.get("snapshot_fields", "f43,f47,f48")),
        snapshot_ut=str(params.get("snapshot_ut", "fa5fd1943c7b386f172d6893dbfba10b")),
        snapshot_headers=as_str_mapping(
            params.get("snapshot_headers"), "params.snapshot_headers"
        ),
        snapshot_params=as_mapping(params.get("snapshot_params"), "params.snapshot_params"),
        price_scale=float(params.get("price_scale", 100.0)),
        reconnect_every_ticks=(
            int(params["reconnect_every_ticks"])
            if params.get("reconnect_every_ticks") is not None
            else None
        ),
        heartbeat_timeout=(
            float(params["heartbeat_timeout"])
            if params.get("heartbeat_timeout") is not None
            else None
        ),
        source_failure_threshold=int(params.get("source_failure_threshold", 2)),
        source_cooldown_seconds=float(params.get("source_cooldown_seconds", 2.0)),
        emit_source_status=to_bool(params.get("emit_source_status"), default=True),
        sources=_build_transport_source(params),
    )
