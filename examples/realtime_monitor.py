from pybt import BacktestEngine, EngineConfig
from pybt.analytics import EquityCurveReporter
from pybt.core.events import FillEvent, SignalEvent
from pybt.data import ADataLiveFeed
from pybt.execution import ImmediateExecutionHandler
from pybt.portfolio import NaivePortfolio
from pybt.risk import MaxPositionRisk
from pybt.strategies import UptrendBreakoutStrategy


def main() -> None:
    SYMBOL = "300502"

    feed = ADataLiveFeed(symbol=SYMBOL, poll_interval=5.0, max_ticks=None)
    strategy = UptrendBreakoutStrategy(symbol=SYMBOL, window=15, breakout_factor=1.5)
    portfolio = NaivePortfolio(lot_size=200)
    execution = ImmediateExecutionHandler(slippage=0.02, commission=15.0)
    risk = MaxPositionRisk(limit=1_000)
    reporter = EquityCurveReporter(initial_cash=100_000.0)

    engine = BacktestEngine(
        data_feed=feed,
        strategies=[strategy],
        portfolio=portfolio,
        execution=execution,
        risk_managers=[risk],
        reporters=[reporter],
        config=EngineConfig(name="live-monitor"),
    )

    def log_signal(event: SignalEvent) -> None:
        print(
            f"[{event.timestamp:%H:%M:%S}] Strategy {event.strategy_id} "
            f"signal: {event.direction} {event.symbol} strength={event.strength:.2f}"
        )

    def log_fill(event: FillEvent) -> None:
        side = "BUY" if event.quantity > 0 else "SELL"
        print(
            f"[{event.timestamp:%H:%M:%S}] {side} {event.symbol} "
            f"qty={abs(event.quantity)} price={event.fill_price:.2f} "
            f"commission={event.commission:.2f}"
        )

    engine.bus.subscribe(SignalEvent, log_signal)
    engine.bus.subscribe(FillEvent, log_fill)
    engine.run()


if __name__ == "__main__":
    main()
