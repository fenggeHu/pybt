"""Component definitions for config-driven engine construction.

This module is the single source of truth for supported config component types
and their parameters. It is used by the web backend to expose `/definitions`
and should stay in sync with `pybt.configuration.loader`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable, Optional


@dataclass(frozen=True)
class ParamDef:
    name: str
    type: str
    required: bool = True
    default: Optional[Any] = None
    description: Optional[str] = None


@dataclass(frozen=True)
class ComponentDef:
    category: str
    type: str
    summary: str
    params: list[ParamDef] = field(default_factory=list)


def list_definitions() -> list[ComponentDef]:
    """Return supported component types for form/documentation generation."""

    market_feed_params = [
        ParamDef(name="symbol", type="str"),
        ParamDef(
            name="source",
            type="str",
            required=False,
            description=(
                "Simple mode source type: sse / api / snapshot_api / snapshot / websocket. "
                "When omitted, feed falls back to advanced sources/default chain."
            ),
        ),
        ParamDef(
            name="url",
            type="str",
            required=False,
            description="Simple mode source URL (mapped to sse_url/snapshot_url/ws url)",
        ),
        ParamDef(
            name="snapshot_fallback",
            type="bool",
            required=False,
            default=True,
            description="Simple mode: add snapshot_api fallback automatically for sse source",
        ),
        ParamDef(
            name="headers",
            type="object",
            required=False,
            description="Simple mode headers for selected source",
        ),
        ParamDef(
            name="field_map",
            type="object",
            required=False,
            description="Simple mode field mapping for selected source",
        ),
        ParamDef(
            name="params",
            type="object",
            required=False,
            description="Simple mode query params for selected source",
        ),
        ParamDef(
            name="snapshot_field_map",
            type="object",
            required=False,
            description="Simple mode: field_map for auto snapshot fallback source",
        ),
        ParamDef(
            name="sse_url",
            type="str",
            required=False,
            description="Override SSE endpoint URL",
        ),
        ParamDef(
            name="secid",
            type="str",
            required=False,
            description="Symbol identity used by source plugins when needed",
        ),
        ParamDef(name="token", type="str", required=False, default=""),
        ParamDef(name="cname", type="str", required=False),
        ParamDef(name="seq", type="int", required=False, default=0),
        ParamDef(name="noop", type="int", required=False, default=0),
        ParamDef(name="max_ticks", type="int", required=False),
        ParamDef(name="max_reconnects", type="int", required=False, default=3),
        ParamDef(name="backoff_seconds", type="float", required=False, default=0.5),
        ParamDef(name="connect_timeout", type="float", required=False, default=5.0),
        ParamDef(name="read_timeout", type="float", required=False, default=30.0),
        ParamDef(
            name="sse_base_url",
            type="str",
            required=False,
            default="https://92.newspush.eastmoney.com/sse",
        ),
        ParamDef(
            name="sse_headers",
            type="object",
            required=False,
            description="Custom SSE request headers; merges with defaults",
        ),
        ParamDef(
            name="reconnect_every_ticks",
            type="int",
            required=False,
            description="Force reconnect after N published ticks",
        ),
        ParamDef(
            name="heartbeat_timeout",
            type="float",
            required=False,
            description="Reconnect if stream stays idle for too long (seconds)",
        ),
        ParamDef(
            name="sources",
            type="list[object]",
            required=False,
            description=(
                "Plugin chain, e.g. [{type:'sse'}, {type:'snapshot_api'}]. "
                "Supported built-ins: sse/api/snapshot_api/websocket/plugin. "
                "Each source can set field_map, e.g. "
                "{price:'data.quote.current',volume:['data.vol','f47']}."
            ),
        ),
        ParamDef(name="snapshot_url", type="str", required=False),
        ParamDef(name="snapshot_fields", type="str", required=False),
        ParamDef(name="snapshot_ut", type="str", required=False),
        ParamDef(
            name="snapshot_headers",
            type="object",
            required=False,
            description="Custom snapshot request headers; merges with defaults",
        ),
        ParamDef(
            name="snapshot_params",
            type="object",
            required=False,
            description="Additional snapshot query params",
        ),
        ParamDef(name="price_scale", type="float", required=False, default=100.0),
    ]

    return [
        ComponentDef(
            category="data_feed",
            type="local_csv",
            summary="CSV/Parquet daily bars",
            params=[
                ParamDef(name="path", type="str", description="CSV/Parquet file path"),
                ParamDef(
                    name="symbol",
                    type="str",
                    required=False,
                    description="Symbol code (defaults to folder name)",
                ),
                ParamDef(
                    name="start",
                    type="str",
                    required=False,
                    description="ISO datetime/date filter (inclusive)",
                ),
                ParamDef(
                    name="end",
                    type="str",
                    required=False,
                    description="ISO datetime/date filter (inclusive)",
                ),
            ],
        ),
        ComponentDef(
            category="data_feed",
            type="local_file",
            summary="CSV/Parquet daily bars (alias of local_csv)",
            params=[
                ParamDef(name="path", type="str", description="CSV/Parquet file path"),
                ParamDef(
                    name="symbol",
                    type="str",
                    required=False,
                    description="Symbol code (defaults to folder name)",
                ),
                ParamDef(
                    name="start",
                    type="str",
                    required=False,
                    description="ISO datetime/date filter (inclusive)",
                ),
                ParamDef(
                    name="end",
                    type="str",
                    required=False,
                    description="ISO datetime/date filter (inclusive)",
                ),
            ],
        ),
        ComponentDef(
            category="data_feed",
            type="inmemory",
            summary="In-memory bars (deterministic)",
            params=[
                ParamDef(
                    name="bars",
                    type="list[bar]",
                    description="Array of bars with timestamp/open/high/low/close",
                ),
            ],
        ),
        ComponentDef(
            category="data_feed",
            type="rest",
            summary="Generic REST polling feed",
            params=[
                ParamDef(name="symbol", type="str"),
                ParamDef(
                    name="url",
                    type="str",
                    description="Endpoint returning JSON with at least {price: float}",
                ),
                ParamDef(
                    name="poll_interval", type="float", required=False, default=1.0
                ),
                ParamDef(name="max_ticks", type="int", required=False),
                ParamDef(name="max_retries", type="int", required=False, default=3),
                ParamDef(
                    name="backoff_seconds", type="float", required=False, default=0.5
                ),
                ParamDef(
                    name="request_timeout",
                    type="float|array|object",
                    required=False,
                    default=5.0,
                    description="Total timeout seconds, [connect,read], or {connect,read}",
                ),
                ParamDef(
                    name="connect_timeout",
                    type="float",
                    required=False,
                    description="REST connect timeout seconds (overrides request_timeout)",
                ),
                ParamDef(
                    name="read_timeout",
                    type="float",
                    required=False,
                    description="REST read timeout seconds (overrides request_timeout)",
                ),
            ],
        ),
        ComponentDef(
            category="data_feed",
            type="websocket",
            summary="Generic WebSocket JSON feed",
            params=[
                ParamDef(name="symbol", type="str"),
                ParamDef(
                    name="url",
                    type="str",
                    description="WebSocket endpoint yielding JSON with at least {price: float}",
                ),
                ParamDef(name="max_ticks", type="int", required=False),
                ParamDef(name="max_reconnects", type="int", required=False, default=3),
                ParamDef(
                    name="backoff_seconds", type="float", required=False, default=0.5
                ),
                ParamDef(name="heartbeat_interval", type="float", required=False),
            ],
        ),
        ComponentDef(
            category="data_feed",
            type="adata",
            summary="AData live polling feed (optional dependency)",
            params=[
                ParamDef(name="symbol", type="str"),
                ParamDef(
                    name="poll_interval", type="float", required=False, default=1.0
                ),
                ParamDef(name="max_ticks", type="int", required=False),
            ],
        ),
        ComponentDef(
            category="data_feed",
            type="eastmoney_sse",
            summary="Eastmoney SSE live feed",
            params=[
                ParamDef(name="symbol", type="str"),
                ParamDef(
                    name="sse_url",
                    type="str",
                    required=False,
                    description="Override SSE endpoint URL",
                ),
                ParamDef(
                    name="secid",
                    type="str",
                    required=False,
                    description="Eastmoney secid; inferred from symbol when omitted",
                ),
                ParamDef(name="token", type="str", required=False, default=""),
                ParamDef(name="cname", type="str", required=False),
                ParamDef(name="seq", type="int", required=False, default=0),
                ParamDef(name="noop", type="int", required=False, default=0),
                ParamDef(name="max_ticks", type="int", required=False),
                ParamDef(name="max_reconnects", type="int", required=False, default=3),
                ParamDef(
                    name="backoff_seconds", type="float", required=False, default=0.5
                ),
                ParamDef(
                    name="connect_timeout", type="float", required=False, default=5.0
                ),
                ParamDef(
                    name="read_timeout", type="float", required=False, default=30.0
                ),
                ParamDef(
                    name="sse_base_url",
                    type="str",
                    required=False,
                    default="https://92.newspush.eastmoney.com/sse",
                ),
                ParamDef(
                    name="sse_headers",
                    type="object",
                    required=False,
                    description="Custom SSE request headers; merges with defaults",
                ),
                ParamDef(name="snapshot_url", type="str", required=False),
                ParamDef(name="snapshot_fields", type="str", required=False),
                ParamDef(name="snapshot_ut", type="str", required=False),
                ParamDef(
                    name="snapshot_headers",
                    type="object",
                    required=False,
                    description="Custom snapshot request headers; merges with defaults",
                ),
                ParamDef(
                    name="snapshot_params",
                    type="object",
                    required=False,
                    description="Additional snapshot query params",
                ),
                ParamDef(
                    name="price_scale", type="float", required=False, default=100.0
                ),
            ],
        ),
        ComponentDef(
            category="data_feed",
            type="market_feed",
            summary="Provider-agnostic pluggable quote feed (SSE/API/WebSocket/plugin)",
            params=market_feed_params,
        ),
        ComponentDef(
            category="data_feed",
            type="eastmoney_sse_ext",
            summary="Legacy alias of market_feed (kept for compatibility)",
            params=market_feed_params,
        ),
        ComponentDef(
            category="strategy",
            type="moving_average",
            summary="Dual moving-average crossover (long/short)",
            params=[
                ParamDef(name="symbol", type="str"),
                ParamDef(name="short_window", type="int", default=5, required=False),
                ParamDef(name="long_window", type="int", default=20, required=False),
                ParamDef(name="strategy_id", type="str", default="mac", required=False),
                ParamDef(
                    name="enabled",
                    type="bool",
                    default=True,
                    required=False,
                    description="Disable strategy when false",
                ),
            ],
        ),
        ComponentDef(
            category="strategy",
            type="uptrend",
            summary="Uptrend breakout (long/flat)",
            params=[
                ParamDef(name="symbol", type="str"),
                ParamDef(name="window", type="int", default=20, required=False),
                ParamDef(
                    name="breakout_factor", type="float", default=1.5, required=False
                ),
                ParamDef(
                    name="strategy_id", type="str", default="uptrend", required=False
                ),
                ParamDef(
                    name="enabled",
                    type="bool",
                    default=True,
                    required=False,
                    description="Disable strategy when false",
                ),
            ],
        ),
        ComponentDef(
            category="strategy",
            type="plugin",
            summary="External strategy class loaded by module path",
            params=[
                ParamDef(
                    name="class_path",
                    type="str",
                    description="Import path in '<module>.<ClassName>' format",
                ),
                ParamDef(
                    name="params",
                    type="object",
                    required=False,
                    default={},
                    description="Keyword args passed to plugin strategy constructor",
                ),
                ParamDef(
                    name="enabled",
                    type="bool",
                    default=True,
                    required=False,
                    description="Disable strategy when false",
                ),
            ],
        ),
        ComponentDef(
            category="portfolio",
            type="naive",
            summary="Fixed lot size portfolio",
            params=[
                ParamDef(name="lot_size", type="int", default=100, required=False),
                ParamDef(
                    name="initial_cash", type="float", default=100_000.0, required=False
                ),
            ],
        ),
        ComponentDef(
            category="execution",
            type="immediate",
            summary="Immediate fills with optional slippage/commission/partial fills",
            params=[
                ParamDef(name="slippage", type="float", default=0.0, required=False),
                ParamDef(name="commission", type="float", default=0.0, required=False),
                ParamDef(
                    name="partial_fill_ratio",
                    type="float",
                    required=False,
                    description="e.g. 0.5 for 50% partial fill",
                ),
                ParamDef(
                    name="max_staleness",
                    type="float",
                    required=False,
                    description="Max seconds since last market tick",
                ),
                ParamDef(
                    name="fill_timing",
                    type="str",
                    default="current_close",
                    required=False,
                    description="current_close (default, has look-ahead) or next_open (realistic)",
                ),
            ],
        ),
        ComponentDef(
            category="risk",
            type="max_position",
            summary="Max absolute position size per symbol",
            params=[ParamDef(name="limit", type="int")],
        ),
        ComponentDef(
            category="risk",
            type="buying_power",
            summary="Buying power limiter (supports leverage)",
            params=[
                ParamDef(
                    name="max_leverage", type="float", default=1.0, required=False
                ),
                ParamDef(
                    name="reserve_cash", type="float", default=0.0, required=False
                ),
                ParamDef(
                    name="initial_cash",
                    type="float",
                    required=False,
                    description="Defaults to portfolio.initial_cash",
                ),
            ],
        ),
        ComponentDef(
            category="risk",
            type="concentration",
            summary="Per-symbol concentration cap",
            params=[
                ParamDef(
                    name="max_fraction", type="float", default=0.5, required=False
                ),
                ParamDef(
                    name="initial_cash",
                    type="float",
                    required=False,
                    description="Defaults to portfolio.initial_cash",
                ),
            ],
        ),
        ComponentDef(
            category="risk",
            type="price_band",
            summary="Rejects orders deviating too far from last price",
            params=[
                ParamDef(name="band_pct", type="float", default=0.05, required=False)
            ],
        ),
        ComponentDef(
            category="reporter",
            type="equity",
            summary="Equity/cash/gross exposure metrics",
            params=[
                ParamDef(
                    name="initial_cash",
                    type="float",
                    required=False,
                    description="Defaults to portfolio.initial_cash",
                ),
            ],
        ),
        ComponentDef(
            category="reporter",
            type="detailed",
            summary="Detailed PnL/drawdown report",
            params=[
                ParamDef(
                    name="initial_cash",
                    type="float",
                    required=False,
                    description="Defaults to portfolio.initial_cash",
                ),
                ParamDef(
                    name="track_equity_curve", type="bool", default=True, required=False
                ),
            ],
        ),
        ComponentDef(
            category="reporter",
            type="tradelog",
            summary="Persist fills to JSONL and/or SQLite",
            params=[
                ParamDef(name="jsonl_path", type="str", required=False),
                ParamDef(name="sqlite_path", type="str", required=False),
            ],
        ),
    ]


def iter_definition_dicts() -> Iterable[dict[str, Any]]:
    """Yield definitions as plain dicts for consumers that avoid dataclasses."""

    for definition in list_definitions():
        yield {
            "category": definition.category,
            "type": definition.type,
            "summary": definition.summary,
            "params": [
                {
                    "name": param.name,
                    "type": param.type,
                    "required": param.required,
                    "default": param.default,
                    "description": param.description,
                }
                for param in definition.params
            ],
        }


__all__ = ["ComponentDef", "ParamDef", "iter_definition_dicts", "list_definitions"]
