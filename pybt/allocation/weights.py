import math
from dataclasses import dataclass
from typing import Dict


@dataclass
class WeightAllocator:
    """Convert target weights into integer position units.

    Parameters
    ----------
    max_leverage : float
        Maximum sum of absolute weights after scaling (e.g. 1.0 for 100% gross, 2.0 for 200%).
    lot_size : int
        Minimum tradable unit (1 share/contract by default).
    rounding : str
        'round' (default), 'floor', or 'ceil' when mapping fractional units to lots.
    allow_short : bool
        If False, negative weights are discarded.
    """

    max_leverage: float = 1.0
    lot_size: int = 1
    rounding: str = "round"
    allow_short: bool = True

    def weights_to_units(self, weights: Dict[str, float], equity: float, prices: Dict[str, float]) -> Dict[str, int]:
        if equity <= 0:
            return {sym: 0 for sym in weights}
        adj: Dict[str, float] = {}
        for sym, w in weights.items():
            if not self.allow_short and w < 0:
                continue
            adj[sym] = float(w)
        if not adj:
            return {}

        total_abs = sum(abs(w) for w in adj.values())
        scale = 1.0
        if self.max_leverage > 0 and total_abs > self.max_leverage and total_abs > 0:
            scale = self.max_leverage / total_abs

        units: Dict[str, int] = {}
        for sym, w in adj.items():
            px = prices.get(sym)
            if px is None or px <= 0:
                continue
            target_value = equity * w * scale
            raw_units = target_value / px
            qty = self._round_units(raw_units)
            units[sym] = qty
        return units

    def _round_units(self, raw_units: float) -> int:
        step = max(1, self.lot_size)
        factor = raw_units / step
        if self.rounding == "floor":
            qty = math.floor(factor) * step
        elif self.rounding == "ceil":
            qty = math.ceil(factor) * step
        else:
            qty = round(factor) * step
        return int(qty)
