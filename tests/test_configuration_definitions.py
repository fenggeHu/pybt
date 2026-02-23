from __future__ import annotations

import json
from pathlib import Path

from pybt.configuration import list_definitions


def _types_for(category: str) -> set[str]:
    return {
        definition.type
        for definition in list_definitions()
        if definition.category == category
    }


def test_data_feed_definitions_cover_builtin_plugins() -> None:
    data_feed_types = _types_for("data_feed")
    assert {
        "local_csv_feed",
        "inmemory_feed",
        "rest_polling_feed",
        "websocket_json_feed",
        "adata_live_feed",
        "eastmoney_marketdata",
        "sina_marketdata",
    }.issubset(data_feed_types)


def test_strategy_definitions_cover_builtin_plugins() -> None:
    strategy_types = _types_for("strategy")
    assert {"moving_average", "uptrend"}.issubset(strategy_types)


def test_eastmoney_marketdata_definition_exposes_transport_params() -> None:
    defs = [d for d in list_definitions() if d.category == "data_feed"]
    target = next(d for d in defs if d.type == "eastmoney_marketdata")
    params = {p.name for p in target.params}
    assert {"symbol", "transport", "url", "field_map"}.issubset(params)


def test_execution_definitions_cover_builtin_plugins() -> None:
    execution_types = _types_for("execution")
    assert {"immediate_execution"}.issubset(execution_types)


def test_portfolio_definitions_cover_builtin_plugins() -> None:
    portfolio_types = _types_for("portfolio")
    assert {"naive_portfolio"}.issubset(portfolio_types)


def test_risk_definitions_cover_builtin_plugins() -> None:
    risk_types = _types_for("risk")
    assert {
        "max_position_risk",
        "buying_power_risk",
        "concentration_risk",
        "price_band_risk",
    }.issubset(risk_types)


def test_reporter_definitions_cover_builtin_plugins() -> None:
    reporter_types = _types_for("reporter")
    assert {"equity_reporter", "detailed_reporter", "tradelog_reporter"}.issubset(
        reporter_types
    )


def test_list_definitions_cache_invalidates_on_registry_change(tmp_path: Path) -> None:
    registry_path = tmp_path / "plugin.jsonc"
    registry_path.write_text(
        json.dumps(
            {
                "version": 1,
                "plugin_dir": ".",
                "plugins": [{"name": "a", "kind": "strategy"}],
            }
        ),
        encoding="utf-8",
    )
    first = list_definitions(registry_path)
    assert {d.type for d in first if d.category == "strategy"} == {"a"}

    registry_path.write_text(
        json.dumps(
            {
                "version": 1,
                "plugin_dir": ".",
                "plugins": [
                    {"name": "a", "kind": "strategy"},
                    {"name": "b", "kind": "strategy"},
                ],
            }
        ),
        encoding="utf-8",
    )

    second = list_definitions(registry_path)
    assert {d.type for d in second if d.category == "strategy"} == {"a", "b"}
