from dataclasses import dataclass
from typing import List, Optional, Tuple

from pybt.data.bar import Bar
from pybt.execution.order import Order


@dataclass
class Fill:
    dt: str  # ISO string for simplicity
    qty: int  # signed quantity (+ buy, - sell)
    price: float
    commission: float
    symbol: str = ""
    tag: str = ""


class SimBroker:
    """Very simple broker that fills to target at the next bar's open.

    Slippage is modeled as bps against the trade direction.
    Commission is per-share flat.
    """

    def __init__(
            self,
            slippage_bps: float = 1.0,
            commission_per_share: float = 0.0,
            commission_rate: float = 0.0,
            volume_limit_pct: float = 1.0,
    ):
        self.slippage_bps = slippage_bps
        self.commission_per_share = commission_per_share
        self.commission_rate = commission_rate
        self.volume_limit_pct = max(0.0, min(volume_limit_pct, 1.0))

    def fill_to_target(self, bar: Bar, current_units: int, target_units: int) -> Optional[Fill]:
        delta = target_units - current_units
        if delta == 0:
            return None
        # Price at open adjusted by slippage against us
        bps = self.slippage_bps / 10_000.0
        px = bar.open * (1.0 + (bps if delta > 0 else -bps))
        commission = abs(delta) * self.commission_per_share + abs(delta * px) * self.commission_rate
        return Fill(dt=bar.dt.isoformat(), qty=delta, price=px, commission=commission, tag="target")

    # --- Extended order model (limit/stop/market) for multi-asset use ---
    def process_orders(
            self,
            symbol: str,
            bar: Bar,
            current_units: int,
            orders: List[Order],
    ) -> Tuple[List[Fill], List[int]]:
        """Process a batch of orders for a single symbol against a day bar.

        Supports MARKET, LIMIT, STOP types; simple partial fills constrained by
        per-bar volume and `allow_partial` flag. Returns (fills, executed_qtys)
        where executed_qtys[i] is the signed quantity filled for orders[i].
        """
        fills: List[Fill] = []
        executed: List[int] = []

        volume_cap: Optional[int] = None
        if self.volume_limit_pct > 0.0 and bar.volume > 0:
            volume_cap = max(1, int(bar.volume * self.volume_limit_pct))
        volume_left = volume_cap

        for order in orders:
            qty = int(order.qty)
            if qty == 0:
                executed.append(0)
                continue

            px = self._determine_fill_price(order, bar)
            if px is None:
                executed.append(0)
                continue

            fill_qty = qty
            if volume_left is not None:
                max_fill = min(abs(qty), volume_left)
                if max_fill <= 0:
                    executed.append(0)
                    continue
                if max_fill < abs(qty) and not order.allow_partial:
                    executed.append(0)
                    continue
                fill_qty = int((max_fill if qty > 0 else -max_fill))

            # Apply slippage against direction
            bps = self.slippage_bps / 10_000.0
            px_adj = px * (1.0 + (bps if fill_qty > 0 else -bps))
            commission = abs(fill_qty) * self.commission_per_share + abs(fill_qty * px_adj) * self.commission_rate
            fill = Fill(dt=bar.dt.isoformat(), qty=fill_qty, price=px_adj, commission=commission, symbol=symbol, tag=order.tag)
            fills.append(fill)
            executed.append(fill_qty)

            if volume_left is not None:
                volume_left = max(0, volume_left - abs(fill_qty))

        return fills, executed

    @staticmethod
    def _determine_fill_price(order: Order, bar: Bar) -> Optional[float]:
        otype = order.type.upper()
        qty = order.qty
        if otype == 'MARKET':
            return bar.open
        if otype == 'LIMIT':
            if order.limit_price is None:
                return None
            lp = float(order.limit_price)
            if qty > 0:
                if bar.low <= lp:
                    return min(lp, bar.open)
            else:
                if bar.high >= lp:
                    return max(lp, bar.open)
            return None
        if otype == 'STOP':
            if order.stop_price is None:
                return None
            sp = float(order.stop_price)
            if qty > 0:
                if bar.high >= sp:
                    return max(sp, bar.open)
            else:
                if bar.low <= sp:
                    return min(sp, bar.open)
            return None
        return None
