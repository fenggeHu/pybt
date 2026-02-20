from datetime import datetime, timedelta
from typing import Any


def build_smoke_config(symbol: str) -> dict[str, Any]:
    start = datetime(2024, 1, 1, 9, 30)
    bars: list[dict[str, Any]] = []
    price = 100.0
    for i in range(5):
        ts = start + timedelta(minutes=i)
        open_price = price
        close_price = price + 0.5
        bars.append(
            {
                "symbol": symbol,
                "timestamp": ts.isoformat(),
                "open": open_price,
                "high": close_price + 0.2,
                "low": open_price - 0.2,
                "close": close_price,
                "volume": 1000 + i,
                "amount": close_price * (1000 + i),
            }
        )
        price = close_price

    return {
        "name": "smoke-realtime",
        "data_feed": {"type": "inmemory", "bars": bars},
        "strategies": [
            {
                "type": "plugin",
                "class_path": "strategies.test_plugins.NoopPluginStrategy",
                "params": {"symbol": symbol, "strategy_id": "smoke-plugin"},
            }
        ],
        "portfolio": {"type": "naive", "lot_size": 100, "initial_cash": 100000},
        "execution": {
            "type": "immediate",
            "slippage": 0.0,
            "commission": 0.0,
            "fill_timing": "next_open",
        },
        "risk": [{"type": "max_position", "limit": 10000}],
        "reporters": [{"type": "equity"}],
    }
