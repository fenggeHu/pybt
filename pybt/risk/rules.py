from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Tuple

from pybt.execution.order import Order
from pybt.portfolio.multi import MultiPortfolio


@dataclass
class RiskConfig:
    max_units_per_symbol: int = 100  # hard cap per symbol
    stop_loss_pct: float = 0.0       # e.g. 0.1 = 10% stop; 0 disables


class RiskManager:
    def __init__(self, cfg: RiskConfig):
        self.cfg = cfg

    def clamp_target_units(self, desired: Dict[str, int]) -> Dict[str, int]:
        if self.cfg.max_units_per_symbol <= 0:
            return desired
        capped: Dict[str, int] = {}
        cap = self.cfg.max_units_per_symbol
        for sym, tgt in desired.items():
            if tgt > cap:
                capped[sym] = cap
            elif tgt < -cap:
                capped[sym] = -cap
            else:
                capped[sym] = tgt
        return capped

    def protective_stop_orders(self, portfolio: MultiPortfolio, latest_prices: Dict[str, float]) -> List[Order]:
        orders: List[Order] = []
        sl = self.cfg.stop_loss_pct
        if sl <= 0:
            return orders
        for sym, units in portfolio.positions.items():
            if units == 0:
                continue
            px = latest_prices.get(sym)
            entry = portfolio.entry_price.get(sym)
            if px is None or entry is None:
                continue
            if units > 0:
                if px <= entry * (1.0 - sl):
                    # Close long
                    orders.append(Order(symbol=sym, qty=-units, type="MARKET", tag="stop_loss"))
            else:
                if px >= entry * (1.0 + sl):
                    # Close short
                    orders.append(Order(symbol=sym, qty=-units, type="MARKET", tag="stop_loss"))
        return orders

