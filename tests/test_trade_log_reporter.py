import json
import sqlite3
from datetime import datetime
from pathlib import Path

from pybt.analytics.trade_log import TradeLogReporter
from pybt.core.event_bus import EventBus
from pybt.core.events import FillEvent


def test_trade_log_writes_jsonl_and_sqlite(tmp_path: Path) -> None:
    jsonl_path = tmp_path / "trades.jsonl"
    sqlite_path = tmp_path / "trades.db"
    reporter = TradeLogReporter(jsonl_path=jsonl_path, sqlite_path=sqlite_path)
    bus = EventBus()
    reporter.bind(bus)
    reporter.on_start()

    fill = FillEvent(
        timestamp=datetime(2024, 1, 1, 0, 0, 0),
        order_id="o1",
        symbol="AAA",
        quantity=10,
        fill_price=100.0,
        commission=1.0,
    )
    reporter.on_fill(fill)
    reporter.on_stop()

    lines = jsonl_path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    record = json.loads(lines[0])
    assert record["order_id"] == "o1"
    assert record["symbol"] == "AAA"

    conn = sqlite3.connect(sqlite_path)
    rows = list(conn.execute("SELECT order_id, symbol, quantity FROM trades"))
    assert rows == [("o1", "AAA", 10)]
    conn.close()
