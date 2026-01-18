"""
Data fetcher using AKShare API.
"""

import asyncio
import pandas as pd
from datetime import datetime, timedelta
from typing import List, Dict, Optional

import akshare as ak

from stock_mcp import config


class StockDataFetcher:
    """Fetch stock data from AKShare."""

    @staticmethod
    async def get_all_stocks_list() -> pd.DataFrame:
        """Get all A-share stocks list."""
        try:
            df = ak.stock_zh_a_spot_em()
            return df
        except Exception as e:
            raise RuntimeError(f"Failed to fetch stock list: {str(e)}")

    @staticmethod
    async def get_stock_history(
        symbol: str,
        start_date: str,
        end_date: str,
        adjust: str = "hfq"
    ) -> pd.DataFrame:
        """
        Get historical data for a stock.

        Args:
            symbol: Stock code (e.g., "600519", "000001")
            start_date: Start date in format "YYYYMMDD"
            end_date: End date in format "YYYYMMDD"
            adjust: Adjustment type ("qfq"=前复权, "hfq"=后复权, ""=不复权)

        Returns:
            DataFrame with historical data
        """
        try:
            df = ak.stock_zh_a_hist(
                symbol=symbol,
                period="daily",
                start_date=start_date,
                end_date=end_date,
                adjust=adjust
            )
            return df
        except Exception as e:
            raise RuntimeError(f"Failed to fetch history for {symbol}: {str(e)}")

    @staticmethod
    async def batch_get_history(
        symbols: List[str],
        start_date: str,
        end_date: str,
        adjust: str = "hfq",
        delay: float = 1.0
    ) -> Dict[str, pd.DataFrame]:
        """
        Batch fetch historical data for multiple stocks.

        Args:
            symbols: List of stock codes
            start_date: Start date in format "YYYYMMDD"
            end_date: End date in format "YYYYMMDD"
            adjust: Adjustment type
            delay: Delay between requests in seconds

        Returns:
            Dict mapping symbol to DataFrame
        """
        results = {}

        for symbol in symbols:
            try:
                df = await StockDataFetcher.get_stock_history(
                    symbol, start_date, end_date, adjust
                )
                results[symbol] = df

                # Be polite to the API
                await asyncio.sleep(delay)

            except Exception as e:
                print(f"Failed to fetch {symbol}: {e}")
                results[symbol] = None

        return results
