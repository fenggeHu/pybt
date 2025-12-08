from ..models import DefinitionItem, DefinitionParam


def list_definitions() -> list[DefinitionItem]:
    """Return supported component types for form auto-generation."""
    return [
        DefinitionItem(
            category="data_feed",
            type="local_csv",
            summary="CSV/Parquet daily bars",
            params=[
                DefinitionParam(name="path", type="str", description="File path for bars"),
                DefinitionParam(name="symbol", type="str", description="Symbol code"),
            ],
        ),
        DefinitionItem(
            category="data_feed",
            type="rest",
            summary="Generic REST polling feed",
            params=[
                DefinitionParam(name="url", type="str", description="Endpoint returning bar data"),
                DefinitionParam(name="interval_secs", type="int", default=5),
            ],
        ),
        DefinitionItem(
            category="data_feed",
            type="websocket",
            summary="Generic WebSocket streaming feed",
            params=[DefinitionParam(name="url", type="str")],
        ),
        DefinitionItem(
            category="strategy",
            type="moving_average",
            summary="Dual moving-average crossover (long only)",
            params=[
                DefinitionParam(name="symbol", type="str"),
                DefinitionParam(name="short_window", type="int", default=5),
                DefinitionParam(name="long_window", type="int", default=20),
            ],
        ),
        DefinitionItem(
            category="strategy",
            type="uptrend",
            summary="Uptrend breakout (long/flat)",
            params=[
                DefinitionParam(name="symbol", type="str"),
                DefinitionParam(name="breakout_lookback", type="int", default=20),
            ],
        ),
        DefinitionItem(
            category="portfolio",
            type="naive",
            summary="Fixed lot size portfolio",
            params=[
                DefinitionParam(name="lot_size", type="int", default=100),
                DefinitionParam(name="initial_cash", type="float", default=100_000.0),
            ],
        ),
        DefinitionItem(
            category="execution",
            type="immediate",
            summary="Immediate fill with optional slippage/commission",
            params=[
                DefinitionParam(name="slippage", type="float", default=0.01),
                DefinitionParam(name="commission", type="float", default=1.0),
                DefinitionParam(name="allow_partial", type="bool", default=False, required=False),
            ],
        ),
        DefinitionItem(
            category="risk",
            type="max_position",
            summary="Max position size limiter",
            params=[DefinitionParam(name="limit", type="int", default=500)],
        ),
        DefinitionItem(
            category="risk",
            type="concentration",
            summary="Concentration cap per symbol",
            params=[
                DefinitionParam(name="max_weight", type="float", default=0.3),
            ],
        ),
        DefinitionItem(
            category="reporter",
            type="equity",
            summary="Equity curve reporter",
            params=[DefinitionParam(name="initial_cash", type="float", default=100_000.0)],
        ),
        DefinitionItem(
            category="reporter",
            type="detailed",
            summary="Detailed PnL/drawdown report",
            params=[
                DefinitionParam(name="initial_cash", type="float", default=100_000.0),
                DefinitionParam(name="track_equity_curve", type="bool", default=True, required=False),
            ],
        ),
    ]
