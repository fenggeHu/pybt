from pybt.core.enums import SignalDirection
from pybt.core.events import MarketEvent, SignalEvent
from pybt.core.interfaces import Strategy


class NoopPluginStrategy(Strategy):
    def __init__(self, symbol: str, strategy_id: str = "plugin-noop") -> None:
        super().__init__()
        self.symbol = symbol
        self.strategy_id = strategy_id
        self._emitted = False

    def on_start(self) -> None:
        self._emitted = False

    def on_market(self, event: MarketEvent) -> None:
        if self._emitted or event.symbol != self.symbol:
            return
        self._emitted = True
        self.bus.publish(
            SignalEvent(
                timestamp=event.timestamp,
                strategy_id=self.strategy_id,
                symbol=self.symbol,
                direction=SignalDirection.LONG,
                strength=1.0,
            )
        )


class NotAStrategy:
    pass
