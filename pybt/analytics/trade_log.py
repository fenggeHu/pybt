import json
import sqlite3
from pathlib import Path
from typing import Optional

from pybt.core.events import FillEvent, MetricsEvent
from pybt.core.interfaces import PerformanceReporter
from pybt.errors import PersistenceError


class TradeLogReporter(PerformanceReporter):
    """Persists fills to JSONL and/or SQLite for auditing."""

    def __init__(
        self,
        jsonl_path: Optional[Path] = None,
        sqlite_path: Optional[Path] = None,
    ) -> None:
        super().__init__()
        if jsonl_path is None and sqlite_path is None:
            raise PersistenceError("At least one of jsonl_path or sqlite_path must be set")
        self.jsonl_path = jsonl_path
        self.sqlite_path = sqlite_path
        self._jsonl_file = None
        self._conn: Optional[sqlite3.Connection] = None

    def on_start(self) -> None:
        if self.jsonl_path is not None:
            self.jsonl_path.parent.mkdir(parents=True, exist_ok=True)
            self._jsonl_file = self.jsonl_path.open("a", encoding="utf-8")
        if self.sqlite_path is not None:
            self.sqlite_path.parent.mkdir(parents=True, exist_ok=True)
            self._conn = sqlite3.connect(self.sqlite_path)
            self._conn.execute(
                """
                CREATE TABLE IF NOT EXISTS trades (
                    ts TEXT,
                    order_id TEXT,
                    symbol TEXT,
                    quantity INTEGER,
                    fill_price REAL,
                    commission REAL,
                    meta TEXT
                )
                """
            )
            self._conn.commit()

    def on_stop(self) -> None:
        if self._jsonl_file:
            self._jsonl_file.close()
            self._jsonl_file = None
        if self._conn:
            self._conn.commit()
            self._conn.close()
            self._conn = None

    def on_fill(self, event: FillEvent) -> None:
        record = {
            "ts": event.timestamp.isoformat(),
            "order_id": event.order_id,
            "symbol": event.symbol,
            "quantity": event.quantity,
            "fill_price": event.fill_price,
            "commission": event.commission,
            "meta": event.meta,
        }
        if self._jsonl_file:
            self._jsonl_file.write(json.dumps(record, ensure_ascii=False) + "\n")
            self._jsonl_file.flush()
        if self._conn:
            self._conn.execute(
                "INSERT INTO trades (ts, order_id, symbol, quantity, fill_price, commission, meta) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    record["ts"],
                    record["order_id"],
                    record["symbol"],
                    record["quantity"],
                    record["fill_price"],
                    record["commission"],
                    json.dumps(record["meta"], ensure_ascii=False),
                ),
            )
            self._conn.commit()

    def emit_metrics(self) -> list[MetricsEvent]:
        return []
