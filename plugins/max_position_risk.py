from __future__ import annotations

from typing import Any, Mapping

from pybt.risk import MaxPositionRisk


def create(params: Mapping[str, Any], ctx: Mapping[str, Any]) -> MaxPositionRisk:
    limit = params.get("limit")
    if limit is None:
        raise ValueError("params.limit is required")
    return MaxPositionRisk(limit=int(limit))
