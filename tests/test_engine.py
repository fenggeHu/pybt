import unittest

from pybt.data.loader import generate_synthetic
from pybt.engine.backtester import run_backtest
from pybt.execution.broker import SimBroker
from pybt.portfolio.portfolio import Portfolio
from pybt.strategy.sma_crossover import SmaCrossStrategy


class TestEngine(unittest.TestCase):
    def test_run_backtest(self):
        bars = generate_synthetic(days=120)
        strat = SmaCrossStrategy(5, 20)
        res = run_backtest(bars, strat, Portfolio(100000), SimBroker())
        self.assertIn('total_return', res.metrics)
        self.assertTrue(len(res.equity_curve) > 0)


if __name__ == '__main__':
    unittest.main()
