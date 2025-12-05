from datetime import datetime

from pybt.core.enums import OrderSide, OrderType
from pybt.core.event_bus import EventBus
from pybt.core.events import MarketEvent, OrderEvent
from pybt.risk.price_band import PriceBandRisk


def test_price_band_rejects_out_of_band_order() -> None:
    risk = PriceBandRisk(band_pct=0.05)
    bus = EventBus()
    risk.bind(bus)
    risk.on_start()

    bus.publish(MarketEvent(timestamp=datetime(2024, 1, 1), symbol="AAA", fields={"close": 100.0}))
    bus.dispatch()

    good = OrderEvent(
        timestamp=datetime(2024, 1, 1),
        symbol="AAA",
        quantity=10,
        order_type=OrderType.LIMIT,
        direction=OrderSide.BUY,
        limit_price=102.0,
    )
    bad = OrderEvent(
        timestamp=datetime(2024, 1, 1),
        symbol="AAA",
        quantity=10,
        order_type=OrderType.LIMIT,
        direction=OrderSide.BUY,
        limit_price=120.0,
    )

    assert risk.review(good) is not None
    assert risk.review(bad) is None
