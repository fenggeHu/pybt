from datetime import datetime

from pybt.core.enums import OrderSide, OrderType
from pybt.core.event_bus import EventBus
from pybt.core.events import FillEvent, MarketEvent, OrderEvent
from pybt.risk.concentration import ConcentrationRisk


def test_concentration_limits_symbol_value() -> None:
    risk = ConcentrationRisk(initial_cash=10_000, max_fraction=0.5)
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
    assert approved.quantity == 50  # 10k equity * 0.5 / 100 price

    # after holding 50, selling is allowed fully
    risk._on_fill(FillEvent(timestamp=datetime(2024, 1, 1), order_id="1", symbol="AAA", quantity=50, fill_price=100.0))
    sell = OrderEvent(
        timestamp=datetime(2024, 1, 2),
        symbol="AAA",
        quantity=50,
        order_type=OrderType.MARKET,
        direction=OrderSide.SELL,
    )
    assert risk.review(sell) is not None
