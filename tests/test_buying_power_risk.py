from datetime import datetime

from pybt.core.enums import OrderSide, OrderType
from pybt.core.event_bus import EventBus
from pybt.core.events import FillEvent, MarketEvent, OrderEvent
from pybt.risk.buying_power import BuyingPowerRisk


def test_buying_power_clips_order() -> None:
    risk = BuyingPowerRisk(initial_cash=10_000, max_leverage=1.0)
    bus = EventBus()
    risk.bind(bus)
    risk.on_start()

    bus.publish(MarketEvent(timestamp=datetime(2024, 1, 1), symbol="AAA", fields={"close": 100.0}))
    bus.dispatch()

    order = OrderEvent(
        timestamp=datetime(2024, 1, 1),
        symbol="AAA",
        quantity=200,
        order_type=OrderType.MARKET,
        direction=OrderSide.BUY,
    )
    approved = risk.review(order)
    assert approved is not None
    assert approved.quantity == 100  # 10k cash / 100 price

    # record fill to update cash, now little buying power
    risk._on_fill(FillEvent(timestamp=datetime(2024, 1, 1), order_id="1", symbol="AAA", quantity=100, fill_price=100.0))
    # next buy should be rejected
    rejected = risk.review(order)
    assert rejected is None
