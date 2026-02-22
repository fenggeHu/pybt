from pybt.configuration import list_definitions


def _types_for(category: str) -> set[str]:
    return {
        definition.type
        for definition in list_definitions()
        if definition.category == category
    }


def test_data_feed_definitions_cover_supported_feed_types() -> None:
    data_feed_types = _types_for("data_feed")
    assert {
        "local_csv",
        "local_file",
        "inmemory",
        "rest",
        "websocket",
        "adata",
        "market_feed",
        "eastmoney_sse",
        "eastmoney_sse_ext",
    }.issubset(data_feed_types)


def test_strategy_definitions_cover_supported_strategy_types() -> None:
    strategy_types = _types_for("strategy")
    assert {"moving_average", "uptrend", "plugin"}.issubset(strategy_types)


def test_strategy_definitions_expose_enabled_flag() -> None:
    defs = [d for d in list_definitions() if d.category == "strategy"]
    assert defs
    for definition in defs:
        params = {p.name for p in definition.params}
        assert "enabled" in params


def test_eastmoney_sse_ext_definitions_expose_extension_params() -> None:
    defs = [d for d in list_definitions() if d.category == "data_feed"]
    target = next(d for d in defs if d.type == "eastmoney_sse_ext")
    params = {p.name for p in target.params}
    assert {"reconnect_every_ticks", "heartbeat_timeout"}.issubset(params)
    assert {"sse_headers", "snapshot_headers", "snapshot_params"}.issubset(params)
    assert "sources" in params


def test_market_feed_definitions_expose_extension_params() -> None:
    defs = [d for d in list_definitions() if d.category == "data_feed"]
    target = next(d for d in defs if d.type == "market_feed")
    params = {p.name for p in target.params}
    assert {"reconnect_every_ticks", "heartbeat_timeout"}.issubset(params)
    assert {"sse_headers", "snapshot_headers", "snapshot_params"}.issubset(params)
    assert {"source", "url", "snapshot_fallback", "headers", "field_map"}.issubset(
        params
    )
    assert "sources" in params


def test_websocket_definitions_expose_reconnect_params() -> None:
    defs = [d for d in list_definitions() if d.category == "data_feed"]
    target = next(d for d in defs if d.type == "websocket")
    params = {p.name for p in target.params}
    assert {"max_reconnects", "backoff_seconds"}.issubset(params)


def test_rest_definitions_expose_timeout_params() -> None:
    defs = [d for d in list_definitions() if d.category == "data_feed"]
    target = next(d for d in defs if d.type == "rest")
    params = {p.name for p in target.params}
    assert {"request_timeout", "connect_timeout", "read_timeout"}.issubset(params)


def test_execution_definitions_cover_supported_execution_types() -> None:
    execution_types = _types_for("execution")
    assert {"immediate"}.issubset(execution_types)


def test_portfolio_definitions_cover_supported_portfolio_types() -> None:
    portfolio_types = _types_for("portfolio")
    assert {"naive"}.issubset(portfolio_types)


def test_risk_definitions_cover_supported_risk_types() -> None:
    risk_types = _types_for("risk")
    assert {
        "max_position",
        "buying_power",
        "concentration",
        "price_band",
    }.issubset(risk_types)


def test_reporter_definitions_cover_supported_reporter_types() -> None:
    reporter_types = _types_for("reporter")
    assert {"equity", "detailed", "tradelog"}.issubset(reporter_types)
