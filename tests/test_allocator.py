import unittest

from pybt.allocation.weights import WeightAllocator


class TestWeightAllocator(unittest.TestCase):
    def test_rounding(self):
        alloc = WeightAllocator(max_leverage=1.0, lot_size=1, rounding='round')
        weights = {'AAPL': 0.5, 'MSFT': 0.5}
        equity = 100_000
        prices = {'AAPL': 150.0, 'MSFT': 250.0}
        units = alloc.weights_to_units(weights, equity, prices)
        self.assertAlmostEqual(units['AAPL'] * 150.0 + units['MSFT'] * 250.0, equity, delta=5000)

    def test_leverage_scale(self):
        alloc = WeightAllocator(max_leverage=1.0)
        weights = {'AAPL': 1.0, 'MSFT': 1.0}
        prices = {'AAPL': 100.0, 'MSFT': 100.0}
        units = alloc.weights_to_units(weights, 100_000, prices)
        gross = abs(units['AAPL'] * 100) + abs(units['MSFT'] * 100)
        self.assertLessEqual(gross / 100_000, 1.05)  # allow rounding tolerance


if __name__ == '__main__':
    unittest.main()
