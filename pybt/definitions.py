"""Component definitions for config-driven engine construction.

This module is the single source of truth for supported config component types
and their parameters. It is used by the web backend to expose `/definitions`
and should stay in sync with `pybt.config`.
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

    return [
        ComponentDef(
            category="data_feed",
            type="local_csv",
            summary="CSV/Parquet daily bars",
            params=[
                ParamDef(name="path", type="str", description="CSV/Parquet file path"),
                ParamDef(name="symbol", type="str", required=False, description="Symbol code (defaults to folder name)"),
                ParamDef(name="start", type="str", required=False, description="ISO datetime/date filter (inclusive)"),
                ParamDef(name="end", type="str", required=False, description="ISO datetime/date filter (inclusive)"),
            ],
        ),
        ComponentDef(
            category="data_feed",
            type="inmemory",
            summary="In-memory bars (deterministic)",
            params=[
                ParamDef(name="bars", type="list[bar]", description="Array of bars with timestamp/open/high/low/close"),
            ],
        ),
        ComponentDef(
            category="data_feed",
            type="rest",
            summary="Generic REST polling feed",
            params=[
                ParamDef(name="symbol", type="str"),
                ParamDef(name="url", type="str", description="Endpoint returning JSON with at least {price: float}"),
                ParamDef(name="poll_interval", type="float", required=False, default=1.0),
                ParamDef(name="max_ticks", type="int", required=False),
            ],
        ),
        ComponentDef(
            category="data_feed",
            type="websocket",
            summary="Generic WebSocket JSON feed",
            params=[
                ParamDef(name="symbol", type="str"),
                ParamDef(name="url", type="str", description="WebSocket endpoint yielding JSON with at least {price: float}"),
                ParamDef(name="max_ticks", type="int", required=False),
                ParamDef(name="heartbeat_interval", type="float", required=False),
            ],
        ),
        ComponentDef(
            category="data_feed",
            type="adata",
            summary="AData live polling feed (optional dependency)",
            params=[
                ParamDef(name="symbol", type="str"),
                ParamDef(name="poll_interval", type="float", required=False, default=1.0),
                ParamDef(name="max_ticks", type="int", required=False),
            ],
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
            ],
        ),
        ComponentDef(
            category="strategy",
            type="uptrend",
            summary="Uptrend breakout (long/flat)",
            params=[
                ParamDef(name="symbol", type="str"),
                ParamDef(name="window", type="int", default=20, required=False),
                ParamDef(name="breakout_factor", type="float", default=1.5, required=False),
                ParamDef(name="strategy_id", type="str", default="uptrend", required=False),
            ],
        ),
        ComponentDef(
            category="portfolio",
            type="naive",
            summary="Fixed lot size portfolio",
            params=[
                ParamDef(name="lot_size", type="int", default=100, required=False),
                ParamDef(name="initial_cash", type="float", default=100_000.0, required=False),
            ],
        ),
        ComponentDef(
            category="execution",
            type="immediate",
            summary="Immediate fills with optional slippage/commission/partial fills",
            params=[
                ParamDef(name="slippage", type="float", default=0.0, required=False),
                ParamDef(name="commission", type="float", default=0.0, required=False),
                ParamDef(name="partial_fill_ratio", type="float", required=False, description="e.g. 0.5 for 50% partial fill"),
                ParamDef(name="max_staleness", type="float", required=False, description="Max seconds since last market tick"),
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
                ParamDef(name="max_leverage", type="float", default=1.0, required=False),
                ParamDef(name="reserve_cash", type="float", default=0.0, required=False),
                ParamDef(name="initial_cash", type="float", required=False, description="Defaults to portfolio.initial_cash"),
            ],
        ),
        ComponentDef(
            category="risk",
            type="concentration",
            summary="Per-symbol concentration cap",
            params=[
                ParamDef(name="max_fraction", type="float", default=0.5, required=False),
                ParamDef(name="initial_cash", type="float", required=False, description="Defaults to portfolio.initial_cash"),
            ],
        ),
        ComponentDef(
            category="risk",
            type="price_band",
            summary="Rejects orders deviating too far from last price",
            params=[ParamDef(name="band_pct", type="float", default=0.05, required=False)],
        ),
        ComponentDef(
            category="reporter",
            type="equity",
            summary="Equity/cash/gross exposure metrics",
            params=[
                ParamDef(name="initial_cash", type="float", required=False, description="Defaults to portfolio.initial_cash"),
            ],
        ),
        ComponentDef(
            category="reporter",
            type="detailed",
            summary="Detailed PnL/drawdown report",
            params=[
                ParamDef(name="initial_cash", type="float", required=False, description="Defaults to portfolio.initial_cash"),
                ParamDef(name="track_equity_curve", type="bool", default=True, required=False),
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
