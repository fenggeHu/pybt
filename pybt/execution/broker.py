from dataclasses import dataclass
from typing import Optional, List

from pybt.data.bar import Bar


@dataclass
class Fill:
    dt: str  # ISO string for simplicity
    qty: int  # signed quantity (+ buy, - sell)
    price: float
    commission: float
    symbol: str = ""


class SimBroker:
    """Very simple broker that fills to target at the next bar's open.

    Slippage is modeled as bps against the trade direction.
    Commission is per-share flat.
    """

    def __init__(self, slippage_bps: float = 1.0, commission_per_share: float = 0.0, commission_rate: float = 0.0):
        self.slippage_bps = slippage_bps
        self.commission_per_share = commission_per_share
        self.commission_rate = commission_rate

    def fill_to_target(self, bar: Bar, current_units: int, target_units: int) -> Optional[Fill]:
        delta = target_units - current_units
        if delta == 0:
            return None
        # Price at open adjusted by slippage against us
        bps = self.slippage_bps / 10_000.0
        px = bar.open * (1.0 + (bps if delta > 0 else -bps))
        commission = abs(delta) * self.commission_per_share + abs(delta * px) * self.commission_rate
        return Fill(dt=bar.dt.isoformat(), qty=delta, price=px, commission=commission)

    # --- Extended order model (limit/stop/market) for multi-asset use ---
    def process_orders(self, symbol: str, bar: Bar, current_units: int, orders: List[dict]) -> List[Fill]:
        """Process a batch of order dicts for a single symbol against a day bar.

        Order dict schema (simple, stdlib-only):
          {
            'type': 'MARKET'|'LIMIT'|'STOP',
            'qty': int (signed),
            'limit_price': float (for LIMIT),
            'stop_price': float (for STOP)
          }
        Returns a list of fills generated today. No partial fills modeled.
        """
        fills: List[Fill] = []
        for od in orders:
            otype = od.get('type', 'MARKET').upper()
            qty = int(od['qty'])
            if qty == 0:
                continue
            # Determine fill eligibility and price
            px: Optional[float] = None
            if otype == 'MARKET':
                px = bar.open
            elif otype == 'LIMIT':
                lp = float(od['limit_price'])
                if qty > 0:
                    # Buy limit fills if low <= lp
                    if bar.low <= lp:
                        px = min(lp, bar.open)
                else:
                    # Sell limit
                    if bar.high >= lp:
                        px = max(lp, bar.open)
            elif otype == 'STOP':
                sp = float(od['stop_price'])
                if qty > 0:
                    # Buy stop triggers if high >= sp; gap handling
                    if bar.high >= sp:
                        px = max(sp, bar.open)
                else:
                    # Sell stop triggers if low <= sp
                    if bar.low <= sp:
                        px = min(sp, bar.open)
            else:
                continue

            if px is None:
                continue  # not filled today

            # Slippage against direction
            bps = self.slippage_bps / 10_000.0
            px_adj = px * (1.0 + (bps if qty > 0 else -bps))
            commission = abs(qty) * self.commission_per_share + abs(qty * px_adj) * self.commission_rate
            fills.append(Fill(dt=bar.dt.isoformat(), qty=qty, price=px_adj, commission=commission, symbol=symbol))
        return fills
