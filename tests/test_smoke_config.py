from pybt.live.smoke import build_smoke_config


def test_build_smoke_config_uses_plugin_strategy() -> None:
    cfg = build_smoke_config(symbol="AAA")
    assert cfg["data_feed"]["type"] == "inmemory"
    assert cfg["strategies"][0]["type"] == "plugin"
    assert (
        cfg["strategies"][0]["class_path"]
        == "strategies.test_plugins.NoopPluginStrategy"
    )
    assert cfg["strategies"][0]["params"]["symbol"] == "AAA"


def test_build_smoke_config_has_multiple_bars() -> None:
    cfg = build_smoke_config(symbol="BBB")
    bars = cfg["data_feed"]["bars"]
    assert len(bars) >= 3
    assert all(bar["symbol"] == "BBB" for bar in bars)
