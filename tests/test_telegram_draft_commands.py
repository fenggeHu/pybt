from apps.telegram_bot.telegram_bot import (
    _build_effective_config,
    _match_strategy_indexes,
    _new_draft_config,
    _normalize_config_name,
    _parse_component_spec,
)


def test_new_draft_config_contains_minimum_sections() -> None:
    cfg = _new_draft_config("000001.SZ")
    assert cfg["data_feed"]["symbol"] == "000001.SZ"
    assert isinstance(cfg["strategies"], list)
    assert cfg["strategies"][0]["type"] == "moving_average"
    assert cfg["portfolio"]["type"] == "naive"
    assert cfg["execution"]["type"] == "immediate"


def test_parse_component_spec_with_json_payload() -> None:
    payload = _parse_component_spec(
        '{"type":"uptrend","symbol":"AAA","window":30}',
        require_type=True,
    )
    assert payload["type"] == "uptrend"
    assert payload["window"] == 30


def test_parse_component_spec_with_key_value_payload() -> None:
    payload = _parse_component_spec(
        "moving_average symbol=AAA short_window=5 long_window=20 enabled=true",
        require_type=True,
    )
    assert payload == {
        "type": "moving_average",
        "symbol": "AAA",
        "short_window": 5,
        "long_window": 20,
        "enabled": True,
    }


def test_parse_component_spec_requires_type() -> None:
    try:
        _parse_component_spec("symbol=AAA short_window=5", require_type=True)
    except ValueError as exc:
        assert "type" in str(exc).lower()
    else:
        raise AssertionError("Expected ValueError for missing type")


def test_normalize_config_name_appends_json_suffix() -> None:
    assert _normalize_config_name("my_live") == "my_live.json"
    assert _normalize_config_name("my_live.json") == "my_live.json"


def test_build_effective_config_filters_disabled_strategies() -> None:
    cfg = _new_draft_config("AAA")
    cfg["strategies"] = [
        {"type": "moving_average", "symbol": "AAA", "enabled": True},
        {"type": "uptrend", "symbol": "AAA", "enabled": False},
    ]
    out = _build_effective_config(cfg)
    assert len(out["strategies"]) == 1
    assert out["strategies"][0]["type"] == "moving_average"
    assert "enabled" not in out["strategies"][0]


def test_match_strategy_indexes_supports_index_id_and_all() -> None:
    strategies = [
        {"type": "moving_average", "strategy_id": "mac-a"},
        {"type": "uptrend", "strategy_id": "up-a"},
    ]
    assert _match_strategy_indexes(strategies, "0") == [0]
    assert _match_strategy_indexes(strategies, "up-a") == [1]
    assert _match_strategy_indexes(strategies, "all") == [0, 1]
