"""
Stock analysis utilities.
"""

from typing import Optional, Dict

import pandas as pd


class StockAnalyzer:
    """Analyze stock data for patterns and trends."""

    @staticmethod
    def calculate_volume_growth(
            df: pd.DataFrame,
            recent_days: int = 3,
            compare_period_days: int = 20
    ) -> Optional[Dict]:
        """
        Calculate volume growth rate.

        Args:
            df: Stock history DataFrame
            recent_days: Number of recent days to average
            compare_period_days: Comparison period in days

        Returns:
            Dict with growth metrics or None if insufficient data
        """
        if len(df) < recent_days + compare_period_days:
            return None

        # Recent N days average
        recent_avg = df.tail(recent_days)['成交量'].mean()

        # Comparison period average
        compare_df = df.tail(compare_period_days).head(-recent_days)
        compare_avg = compare_df['成交量'].mean()

        # Calculate growth rate
        if compare_avg == 0:
            return None

        growth_rate = (recent_avg - compare_avg) / compare_avg * 100

        # Calculate amount growth
        recent_amount_avg = df.tail(recent_days)['成交额'].mean()
        compare_amount_avg = compare_df['成交额'].mean()
        amount_growth = (recent_amount_avg - compare_amount_avg) / compare_amount_avg * 100

        return {
            'volume_growth_rate': round(growth_rate, 2),
            'amount_growth_rate': round(amount_growth, 2),
            'recent_avg_volume': round(recent_avg, 0),
            'compare_avg_volume': round(compare_avg, 0),
            'recent_avg_amount': round(recent_amount_avg, 2),
            'compare_avg_amount': round(compare_amount_avg, 2)
        }

    @staticmethod
    def calculate_amount_growth(
            df: pd.DataFrame,
            recent_days: int = 3,
            compare_period_days: int = 20
    ) -> Optional[Dict]:
        """Calculate trading amount growth rate."""
        # Similar to calculate_volume_growth but focused on amount
        return StockAnalyzer.calculate_volume_growth(
            df, recent_days, compare_period_days
        )

    @staticmethod
    def find_surge_events(
            df: pd.DataFrame,
            threshold: float = 2.0,
            window: int = 20
    ) -> pd.DataFrame:
        """
        Find volume surge events.

        Args:
            df: Stock history DataFrame
            threshold: Threshold multiplier (e.g., 2.0 = 2x average)
            window: Moving average window

        Returns:
            DataFrame with surge events
        """
        # Calculate moving average
        df = df.copy()
        df['ma_volume'] = df['成交量'].rolling(window=window).mean()

        # Find surges
        surges = df[df['成交量'] > df['ma_volume'] * threshold]

        return surges[['日期', '收盘', '成交量', '成交额', '涨跌幅']]

    @staticmethod
    def analyze_price_trend(
            df: pd.DataFrame,
            days: int = 5
    ) -> Optional[Dict]:
        """
        Analyze price trend.

        Args:
            df: Stock history DataFrame
            days: Number of days to analyze

        Returns:
            Dict with trend metrics or None
        """
        if len(df) < days:
            return None

        recent = df.tail(days)
        start_price = recent['收盘'].iloc[0]
        end_price = recent['收盘'].iloc[-1]

        if start_price == 0:
            return None

        price_change = (end_price - start_price) / start_price * 100

        # Calculate volatility
        daily_returns = recent['收盘'].pct_change().dropna()
        volatility = daily_returns.std() * 100 if len(daily_returns) > 0 else 0

        return {
            'days': days,
            'price_change': round(price_change, 2),
            'start_price': round(start_price, 2),
            'end_price': round(end_price, 2),
            'volatility': round(volatility, 2)
        }
