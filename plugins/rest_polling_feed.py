from __future__ import annotations

from typing import Any, Mapping, Sequence

from pybt.data import RESTPollingFeed

from pybt.configuration.plugin_helpers import require_str


def _parse_request_timeout(params: Mapping[str, Any]) -> float | tuple[float, float]:
    connect_timeout = params.get("connect_timeout")
    read_timeout = params.get("read_timeout")
    if connect_timeout is not None or read_timeout is not None:
        return (
            float(connect_timeout if connect_timeout is not None else 5.0),
            float(read_timeout if read_timeout is not None else 5.0),
        )

    timeout = params.get("request_timeout", 5.0)
    if isinstance(timeout, (int, float)):
        return float(timeout)
    if isinstance(timeout, Mapping):
        connect = timeout.get("connect", timeout.get("connect_timeout", 5.0))
        read = timeout.get("read", timeout.get("read_timeout", 5.0))
        return (float(connect), float(read))
    if isinstance(timeout, Sequence) and not isinstance(timeout, (str, bytes, bytearray)):
        values = list(timeout)
        if len(values) != 2:
            raise ValueError("params.request_timeout array must contain 2 numbers")
        return (float(values[0]), float(values[1]))
    raise ValueError(
        "params.request_timeout must be number, [connect,read], or object"
    )


def create(params: Mapping[str, Any], ctx: Mapping[str, Any]) -> RESTPollingFeed:
    return RESTPollingFeed(
        symbol=require_str(params, "symbol"),
        url=require_str(params, "url"),
        poll_interval=float(params.get("poll_interval", 1.0)),
        max_ticks=params.get("max_ticks"),
        max_retries=int(params.get("max_retries", 3)),
        backoff_seconds=float(params.get("backoff_seconds", 0.5)),
        request_timeout=_parse_request_timeout(params),
    )
