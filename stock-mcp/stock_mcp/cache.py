"""
SQLite-based cache for stock data.
"""

import sqlite3
import pandas as pd
from pathlib import Path
from datetime import datetime
from typing import Optional

from stock_mcp import config


class StockDataCache:
    """Cache for stock data using SQLite."""

    def __init__(self, db_path: str):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self):
        """Initialize database tables."""
        with sqlite3.connect(self.db_path) as conn:
            # Stock history table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS stock_history (
                    symbol TEXT,
                    date TEXT,
                    open REAL,
                    high REAL,
                    low REAL,
                    close REAL,
                    volume REAL,
                    amount REAL,
                    pct_change REAL,
                    turnover REAL,
                    PRIMARY KEY (symbol, date)
                )
            """)

            # Stock list table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS stock_list (
                    symbol TEXT PRIMARY KEY,
                    name TEXT,
                    market TEXT,
                    last_update TEXT
                )
            """)

            # Indexes
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_symbol_date
                ON stock_history(symbol, date)
            """)

            conn.commit()

    def save_stock_history(self, symbol: str, df: pd.DataFrame) -> None:
        """Save stock history data to cache."""
        df = df.copy()
        df['symbol'] = symbol

        # Rename columns to match database schema
        column_map = {
            '开盘': 'open',
            '最高': 'high',
            '最低': 'low',
            '收盘': 'close',
            '成交量': 'volume',
            '成交额': 'amount',
            '涨跌幅': 'pct_change',
            '换手率': 'turnover',
            '日期': 'date'
        }
        df = df.rename(columns=column_map)

        # Ensure required columns exist
        required_cols = ['symbol', 'date', 'open', 'high', 'low', 'close',
                       'volume', 'amount', 'pct_change', 'turnover']
        for col in required_cols:
            if col not in df.columns:
                df[col] = None

        # Save to database
        with sqlite3.connect(self.db_path) as conn:
            # Delete existing data for this symbol and date range
            if not df.empty:
                min_date = df['date'].min()
                max_date = df['date'].max()
                conn.execute("""
                    DELETE FROM stock_history
                    WHERE symbol = ? AND date BETWEEN ? AND ?
                """, (symbol, min_date, max_date))

            # Insert new data
            df[required_cols].to_sql('stock_history', conn, if_exists='append',
                                  index=False)
            conn.commit()

    def get_stock_history(
        self,
        symbol: str,
        start_date: str,
        end_date: str
    ) -> Optional[pd.DataFrame]:
        """Get stock history from cache."""
        with sqlite3.connect(self.db_path) as conn:
            query = """
                SELECT * FROM stock_history
                WHERE symbol = ? AND date BETWEEN ? AND ?
                ORDER BY date
            """
            df = pd.read_sql(query, conn, params=(symbol, start_date, end_date))

        if df.empty:
            return None
        return df

    def save_stock_list(self, df: pd.DataFrame) -> None:
        """Save stock list to cache."""
        df = df.copy()
        df['last_update'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        # Rename columns
        column_map = {
            '代码': 'symbol',
            '名称': 'name',
            '最新价': 'price',
            '涨跌幅': 'pct_change',
            '涨跌额': 'change',
            '成交量': 'volume',
            '成交额': 'amount',
            '振幅': 'amplitude',
            '最高': 'high',
            '最低': 'low',
            '今开': 'open',
            '昨收': 'pre_close'
        }

        # Try to map columns if they exist
        for chinese_col, english_col in column_map.items():
            if chinese_col in df.columns:
                df = df.rename(columns={chinese_col: english_col})

        # Ensure required columns
        if 'market' not in df.columns:
            df['market'] = df['symbol'].apply(
                lambda x: 'SH' if x.startswith('6') else 'SZ'
            )

        with sqlite3.connect(self.db_path) as conn:
            df.to_sql('stock_list', conn, if_exists='replace', index=False)
            conn.commit()

    def get_stock_list(self) -> Optional[pd.DataFrame]:
        """Get stock list from cache."""
        with sqlite3.connect(self.db_path) as conn:
            try:
                df = pd.read_sql("SELECT * FROM stock_list", conn)
                return df if not df.empty else None
            except Exception:
                return None

    def is_cache_fresh(self, days: int = 1) -> bool:
        """Check if stock list cache is fresh."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT MAX(last_update) FROM stock_list")
            result = cursor.fetchone()[0]

        if not result:
            return False

        last_update = datetime.strptime(result, '%Y-%m-%d %H:%M:%S')
        return (datetime.now() - last_update).days <= days

    def get_cache_stats(self) -> dict:
        """Get cache statistics."""
        with sqlite3.connect(self.db_path) as conn:
            # Count stocks with data
            cursor = conn.cursor()
            cursor.execute("""
                SELECT COUNT(DISTINCT symbol) FROM stock_history
            """)
            stock_count = cursor.fetchone()[0]

            # Count stock list entries
            cursor.execute("SELECT COUNT(*) FROM stock_list")
            list_count = cursor.fetchone()[0]

            # Get date range
            cursor.execute("""
                SELECT MIN(date), MAX(date) FROM stock_history
            """)
            date_range = cursor.fetchone()

            # Get database size
            db_size = self.db_path.stat().st_size if self.db_path.exists() else 0

            return {
                "cached_stocks": stock_count,
                "stock_list_count": list_count,
                "date_range": {
                    "min": date_range[0],
                    "max": date_range[1]
                },
                "database_size_bytes": db_size,
                "database_path": str(self.db_path)
            }
