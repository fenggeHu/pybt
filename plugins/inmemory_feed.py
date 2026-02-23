from __future__ import annotations

from datetime import datetime
from typing import Any, Mapping

from pybt.core.models import Bar
from pybt.data import InMemoryBarFeed

from pybt.configuration.plugin_helpers import as_object_array, parse_optional_dt


def create(params: Mapping[str, Any], ctx: Mapping[str, Any]) -> InMemoryBarFeed:
    raw_bars = as_object_array(params.get("bars"), "params.bars")
    if not raw_bars:
        raise ValueError("params.bars is required")

    bars: list[Bar] = []
    for idx, raw in enumerate(raw_bars):
        ts = parse_optional_dt(raw.get("timestamp"))
        if ts is None:
            raise ValueError(f"params.bars[{idx}].timestamp is required")
        assert isinstance(ts, datetime)
        symbol = str(raw.get("symbol") or "").strip()
        if not symbol:
            raise ValueError(f"params.bars[{idx}].symbol is required")
        bars.append(
            Bar(
                symbol=symbol,
                timestamp=ts,
                open=float(raw.get("open")),
                high=float(raw.get("high")),
                low=float(raw.get("low")),
                close=float(raw.get("close")),
                volume=float(raw.get("volume", 0.0)),
                amount=float(raw.get("amount", 0.0)),
            )
        )
    return InMemoryBarFeed(bars)
