from __future__ import annotations

from typing import Any, Mapping

from pybt.data import LocalCSVBarFeed

from pybt.configuration.plugin_helpers import parse_optional_dt, to_path


def create(params: Mapping[str, Any], ctx: Mapping[str, Any]) -> LocalCSVBarFeed:
    path = to_path(params.get("path"), "params.path")
    symbol = params.get("symbol")
    if symbol is not None:
        symbol = str(symbol)
    return LocalCSVBarFeed(
        path=path,
        symbol=symbol,
        start=parse_optional_dt(params.get("start")),
        end=parse_optional_dt(params.get("end")),
    )
