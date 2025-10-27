"""
Strategy implementations.
"""

from .moving_average import MovingAverageCrossStrategy
from .uptrend import UptrendBreakoutStrategy

__all__ = ["MovingAverageCrossStrategy", "UptrendBreakoutStrategy"]
