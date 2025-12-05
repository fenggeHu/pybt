from datetime import datetime

from pybt.core.events import FillEvent, OrderEvent
from pybt.core.enums import OrderSide, OrderType
from pybt.core.event_bus import EventBus
from pybt.risk.position import MaxPositionRisk


def _order(qty: int) -> OrderEvent:
    return OrderEvent(
        timestamp=datetime(2024, 1, 1),
        symbol="AAA",
        quantity=qty,
        order_type=OrderType.MARKET,
        direction=OrderSide.BUY if qty > 0 else OrderSide.SELL,
    )


def test_max_position_limits_and_updates() -> None:
    risk = MaxPositionRisk(limit=100)
    bus = EventBus()
    risk.bind(bus)
    risk.on_start()

    # first order within limit passes untouched
    approved = risk.review(_order(80))
    assert approved is not None and approved.quantity == 80

    # record fill to update positions
    risk._on_fill(FillEvent(timestamp=datetime(2024, 1, 1), order_id="1", symbol="AAA", quantity=80, fill_price=10.0))

    # next order exceeds limit, should be clipped to 20
    approved = risk.review(_order(50))
    assert approved is not None and approved.quantity == 20

    # selling back frees capacity
    risk._on_fill(FillEvent(timestamp=datetime(2024, 1, 1), order_id="2", symbol="AAA", quantity=-50, fill_price=10.0))
    approved = risk.review(_order(80))
    assert approved is not None and approved.quantity == 70
