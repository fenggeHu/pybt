from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Optional

from pybt.execution.broker import Fill


@dataclass
class Trade:
    symbol: str
    side: str  # 'LONG' or 'SHORT'
    qty: int   # positive executed quantity for this roundtrip (absolute)
    entry_dt: str
    entry_px: float
    exit_dt: str
    exit_px: float
    pnl: float
    ret: float
    holding_days: int


class TradeLedger:
    """Tracks round-trip trades per symbol using average cost basis.

    - Aggregates adds into weighted average entry price and accumulated entry commissions.
    - On reductions, realizes proportional PnL and allocates proportional entry commissions.
    - On flips, closes remaining side then opens new side.
    Simplified (not FIFO), but stable and stdlib-only.
    """

    def __init__(self):
        self.state: Dict[str, Dict[str, object]] = {}
        self.trades: List[Trade] = []

    def on_fill(self, f: Fill) -> None:
        sym = f.symbol or "ASSET"
        st = self.state.get(sym, {"units": 0, "entry_px": 0.0, "entry_dt": "", "entry_comm": 0.0})
        units = int(st["units"])  # signed
        entry_px = float(st["entry_px"]) if units != 0 else 0.0
        entry_dt = str(st["entry_dt"]) if units != 0 else ""
        entry_comm = float(st["entry_comm"]) if units != 0 else 0.0

        qty = int(f.qty)
        if qty == 0:
            return

        # Same-side add or reduce
        if units == 0 or (units > 0 and qty > 0) or (units < 0 and qty < 0):
            # Add to position: update weighted average price and entry commission
            new_units = units + qty
            if units == 0:
                entry_px = f.price
                entry_dt = f.dt
                entry_comm = f.commission
            else:
                w_old = abs(units)
                w_new = abs(qty)
                entry_px = (entry_px * w_old + f.price * w_new) / (w_old + w_new)
                entry_comm += f.commission
            self.state[sym] = {"units": new_units, "entry_px": entry_px, "entry_dt": entry_dt, "entry_comm": entry_comm}
            return

        # Opposite-side: reduce or flip
        remaining = units + qty  # since qty has opposite sign
        closing_qty = abs(qty) if abs(qty) <= abs(units) else abs(units)
        # Proportional allocation of entry commissions
        alloc_comm = entry_comm * (closing_qty / abs(units)) if units != 0 else 0.0
        realized_comm = alloc_comm + f.commission

        side = "LONG" if units > 0 else "SHORT"
        # PnL for the executed closing quantity
        if side == "LONG":
            pnl_gross = (f.price - entry_px) * closing_qty
            ret = (f.price / entry_px - 1.0) if entry_px != 0 else 0.0
        else:
            pnl_gross = (entry_px - f.price) * closing_qty
            ret = (entry_px / f.price - 1.0) if f.price != 0 else 0.0

        pnl_net = pnl_gross - realized_comm
        # Holding days: from entry_dt to this fill dt
        try:
            d0 = datetime.fromisoformat(entry_dt)
            d1 = datetime.fromisoformat(f.dt)
            holding_days = (d1.date() - d0.date()).days
        except Exception:
            holding_days = 0

        self.trades.append(
            Trade(
                symbol=sym,
                side=side,
                qty=closing_qty,
                entry_dt=entry_dt,
                entry_px=entry_px,
                exit_dt=f.dt,
                exit_px=f.price,
                pnl=pnl_net,
                ret=ret,
                holding_days=holding_days,
            )
        )

        # Update/flip remaining position
        if remaining == 0:
            # Closed fully
            self.state[sym] = {"units": 0, "entry_px": 0.0, "entry_dt": "", "entry_comm": 0.0}
        elif (units > 0 and remaining > 0) or (units < 0 and remaining < 0):
            # Partial reduce, same side remains -> keep avg entry, reduce entry_comm
            new_comm = entry_comm - alloc_comm
            self.state[sym] = {"units": remaining, "entry_px": entry_px, "entry_dt": entry_dt, "entry_comm": new_comm}
        else:
            # Flip: after closing existing abs(units), leftover opens new side at this fill price
            open_qty = abs(remaining)
            new_side_entry = f.price
            self.state[sym] = {"units": remaining, "entry_px": new_side_entry, "entry_dt": f.dt, "entry_comm": 0.0}

    def get_trades(self) -> List[Trade]:
        return list(self.trades)

