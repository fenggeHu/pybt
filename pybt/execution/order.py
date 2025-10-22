from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class Order:
    symbol: str
    qty: int  # signed
    type: str = "MARKET"  # MARKET | LIMIT | STOP
    limit_price: Optional[float] = None
    stop_price: Optional[float] = None
    tag: str = ""
    allow_partial: bool = True
    time_in_force: str = "DAY"  # DAY | GTC | IOC

    def to_dict(self) -> dict:
        d = {"type": self.type, "qty": self.qty, "allow_partial": self.allow_partial, "time_in_force": self.time_in_force, "tag": self.tag}
        if self.limit_price is not None:
            d["limit_price"] = float(self.limit_price)
        if self.stop_price is not None:
            d["stop_price"] = float(self.stop_price)
        return d

    def with_qty(self, qty: int) -> "Order":
        return Order(
            symbol=self.symbol,
            qty=qty,
            type=self.type,
            limit_price=self.limit_price,
            stop_price=self.stop_price,
            tag=self.tag,
            allow_partial=self.allow_partial,
            time_in_force=self.time_in_force,
        )
