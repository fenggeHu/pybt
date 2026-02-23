from __future__ import annotations

from typing import Any, Mapping

from pybt.risk import PriceBandRisk


def create(params: Mapping[str, Any], ctx: Mapping[str, Any]) -> PriceBandRisk:
    return PriceBandRisk(band_pct=float(params.get("band_pct", 0.05)))
