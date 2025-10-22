import unittest

from pybt.indicators.basic import SMA, EMA


class TestIndicators(unittest.TestCase):
    def test_sma(self):
        sma = SMA(3)
        vals = [1, 2, 3, 4]
        outs = [sma.update(x) for x in vals]
        self.assertIsNone(outs[0])
        self.assertIsNone(outs[1])
        self.assertAlmostEqual(outs[2], 2.0)
        self.assertAlmostEqual(outs[3], 3.0)

    def test_ema(self):
        ema = EMA(3)
        v1 = ema.update(1)
        v2 = ema.update(2)
        self.assertGreater(v2, v1)


if __name__ == '__main__':
    unittest.main()
