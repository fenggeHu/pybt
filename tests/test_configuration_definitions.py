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
        "eastmoney_sse",
    }.issubset(data_feed_types)


def test_strategy_definitions_cover_supported_strategy_types() -> None:
    strategy_types = _types_for("strategy")
    assert {"moving_average", "uptrend", "plugin"}.issubset(strategy_types)


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
