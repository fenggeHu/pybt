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

    def to_dict(self) -> dict:
        d = {"type": self.type, "qty": self.qty}
        if self.limit_price is not None:
            d["limit_price"] = float(self.limit_price)
        if self.stop_price is not None:
            d["stop_price"] = float(self.stop_price)
        return d
