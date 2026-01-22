"""
MCP tool registration for stock analysis.
"""

import json
from typing import Optional

from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel, Field, ConfigDict

from . import config
from .analyzer import StockAnalyzer
from .cache import StockDataCache
from .fetcher import StockDataFetcher


# ===== Input Models =====

class GetStockListInput(BaseModel):
    """Input model for getting stock list."""
    model_config = ConfigDict(
        str_strip_whitespace=True,
        validate_assignment=True
    )

    force_refresh: bool = Field(
        default=False,
        description="Force refresh from API even if cache is fresh"
    )


class GetStockHistoryInput(BaseModel):
    """Input model for getting stock history."""
    model_config = ConfigDict(
        str_strip_whitespace=True,
        validate_assignment=True
    )

    symbol: str = Field(
        ...,
        description="Stock code (e.g., '600519', '000001')",
        min_length=6,
        max_length=6
    )

    start_date: str = Field(
        ...,
        description="Start date in format 'YYYYMMDD' (e.g., '20240101')",
        min_length=8,
        max_length=8
    )

    end_date: str = Field(
        ...,
        description="End date in format 'YYYYMMDD' (e.g., '20241231')",
        min_length=8,
        max_length=8
    )

    adjust: str = Field(
        default="hfq",
        description="Price adjustment: 'hfq'=后复权, 'qfq'=前复权, ''=不复权",
        pattern="^(hfq|qfq|)?$"
    )

    force_refresh: bool = Field(
        default=False,
        description="Force fetch from API even if cached"
    )


class AnalyzeVolumeSurgeInput(BaseModel):
    """Input model for volume surge analysis."""
    model_config = ConfigDict(
        str_strip_whitespace=True,
        validate_assignment=True
    )

    symbol: str = Field(
        ...,
        description="Stock code (e.g., '600519', '000001')",
        min_length=6,
        max_length=6
    )

    start_date: str = Field(
        ...,
        description="Start date in format 'YYYYMMDD'",
        min_length=8,
        max_length=8
    )

    end_date: str = Field(
        ...,
        description="End date in format 'YYYYMMDD'",
        min_length=8,
        max_length=8
    )

    recent_days: int = Field(
        default=config.DEFAULT_RECENT_DAYS,
        description="Number of recent days to analyze (default: 3)",
        ge=1,
        le=30
    )

    compare_period: int = Field(
        default=config.DEFAULT_COMPARE_PERIOD,
        description="Comparison period in days (default: 20)",
        ge=5,
        le=60
    )

    force_refresh: bool = Field(
        default=False,
        description="Force fetch from API even if cached"
    )


class AnalyzeAmountSurgeInput(BaseModel):
    """Input model for amount surge analysis."""
    model_config = ConfigDict(
        str_strip_whitespace=True,
        validate_assignment=True
    )

    symbol: str = Field(
        ...,
        description="Stock code (e.g., '600519', '000001')",
        min_length=6,
        max_length=6
    )

    start_date: str = Field(
        ...,
        description="Start date in format 'YYYYMMDD'",
        min_length=8,
        max_length=8
    )

    end_date: str = Field(
        ...,
        description="End date in format 'YYYYMMDD'",
        min_length=8,
        max_length=8
    )

    recent_days: int = Field(
        default=config.DEFAULT_RECENT_DAYS,
        description="Number of recent days to analyze (default: 3)",
        ge=1,
        le=30
    )

    compare_period: int = Field(
        default=config.DEFAULT_COMPARE_PERIOD,
        description="Comparison period in days (default: 20)",
        ge=5,
        le=60
    )

    force_refresh: bool = Field(
        default=False,
        description="Force fetch from API even if cached"
    )


class ScreenStocksInput(BaseModel):
    """Input model for screening stocks."""
    model_config = ConfigDict(
        str_strip_whitespace=True,
        validate_assignment=True
    )

    start_date: str = Field(
        ...,
        description="Start date in format 'YYYYMMDD'",
        min_length=8,
        max_length=8
    )

    end_date: str = Field(
        ...,
        description="End date in format 'YYYYMMDD'",
        min_length=8,
        max_length=8
    )

    criterion: str = Field(
        default="volume_surge",
        description="Screening criterion: 'volume_surge' or 'amount_surge'",
        pattern="^(volume_surge|amount_surge)$"
    )

    threshold: float = Field(
        default=config.DEFAULT_VOLUME_THRESHOLD,
        description="Growth rate threshold in percent (default: 50.0)",
        ge=0,
        le=500
    )

    recent_days: int = Field(
        default=config.DEFAULT_RECENT_DAYS,
        description="Number of recent days to analyze (default: 3)",
        ge=1,
        le=30
    )

    compare_period: int = Field(
        default=config.DEFAULT_COMPARE_PERIOD,
        description="Comparison period in days (default: 20)",
        ge=5,
        le=60
    )

    limit: int = Field(
        default=20,
        description="Maximum results to return (default: 20)",
        ge=1,
        le=100
    )

    force_refresh: bool = Field(
        default=False,
        description="Force fetch from API even if cached"
    )


class UpdateCacheInput(BaseModel):
    """Input model for updating cache."""
    model_config = ConfigDict(
        str_strip_whitespace=True,
        validate_assignment=True
    )

    symbols: Optional[str] = Field(
        default=None,
        description="Comma-separated stock codes (e.g., '600519,000001'). If None, updates all stocks from list."
    )

    start_date: str = Field(
        ...,
        description="Start date in format 'YYYYMMDD'",
        min_length=8,
        max_length=8
    )

    end_date: str = Field(
        ...,
        description="End date in format 'YYYYMMDD'",
        min_length=8,
        max_length=8
    )


class GetCacheStatusInput(BaseModel):
    """Input model for getting cache status."""
    model_config = ConfigDict(
        str_strip_whitespace=True,
        validate_assignment=True
    )

    detailed: bool = Field(
        default=False,
        description="Return detailed statistics including date range and database size"
    )


# ===== Tool Registrations =====

def register_get_stock_list(mcp: FastMCP, cache: StockDataCache) -> None:
    """Register get_stock_list tool."""

    @mcp.tool(
        name="get_stock_list",
        annotations={
            "title": "Get A-Share Stock List",
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False
        }
    )
    async def get_stock_list_tool(params: GetStockListInput) -> str:
        """
        Get all A-share stock list from cache or API.

        This tool retrieves the complete list of A-share stocks including
        Shanghai and Shenzhen markets. Results include stock codes, names,
        and basic trading information.

        Args:
            params: Input parameters with optional force_refresh flag

        Returns:
            JSON-formatted string with stock list data

        Error Handling:
            - Returns "Error: Failed to fetch stock list" if API call fails
            - Returns cached data if available and force_refresh=False
        """
        try:
            # Try cache first
            if not params.force_refresh:
                if cache.is_cache_fresh(days=config.CACHE_DAYS):
                    df = cache.get_stock_list()
                    if df is not None and not df.empty:
                        return json.dumps({
                            "source": "cache",
                            "count": len(df),
                            "stocks": df.to_dict('records')[:100]  # Limit to 100 for readability
                        }, ensure_ascii=False, indent=2)

            # Fetch from API
            df = await StockDataFetcher.get_all_stocks_list()
            cache.save_stock_list(df)

            return json.dumps({
                "source": "api",
                "count": len(df),
                "stocks": df.to_dict('records')[:100]
            }, ensure_ascii=False, indent=2)

        except Exception as e:
            return f"Error: Failed to fetch stock list: {str(e)}"


def register_get_stock_history(mcp: FastMCP, cache: StockDataCache) -> None:
    """Register get_stock_history tool."""

    @mcp.tool(
        name="get_stock_history",
        annotations={
            "title": "Get Stock Historical Data",
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False
        }
    )
    async def get_stock_history_tool(params: GetStockHistoryInput) -> str:
        """
        Get historical trading data for a specific stock.

        This tool retrieves daily OHLCV (Open, High, Low, Close, Volume)
        data for a given stock code. Data includes prices, volume, trading amount,
        and price changes.

        Args:
            params: Input parameters including symbol, dates, adjustment type

        Returns:
            JSON-formatted string with historical data

        Error Handling:
            - Returns "Error: Invalid stock code format" if symbol validation fails
            - Returns "Error: Failed to fetch history for {symbol}" if API fails
            - Returns cached data if available and force_refresh=False
        """
        try:
            # Try cache first
            if not params.force_refresh:
                cached_df = cache.get_stock_history(
                    params.symbol,
                    params.start_date,
                    params.end_date
                )
                if cached_df is not None and not cached_df.empty:
                    return json.dumps({
                        "source": "cache",
                        "symbol": params.symbol,
                        "count": len(cached_df),
                        "data": cached_df.to_dict('records')
                    }, ensure_ascii=False, indent=2)

            # Fetch from API
            df = await StockDataFetcher.get_stock_history(
                params.symbol,
                params.start_date,
                params.end_date,
                params.adjust
            )

            if df is None or df.empty:
                return f"Error: No data found for stock {params.symbol}"

            cache.save_stock_history(params.symbol, df)

            return json.dumps({
                "source": "api",
                "symbol": params.symbol,
                "count": len(df),
                "data": df.to_dict('records')
            }, ensure_ascii=False, indent=2)

        except Exception as e:
            return f"Error: Failed to fetch history for {params.symbol}: {str(e)}"


def register_analyze_volume_surge(mcp: FastMCP, cache: StockDataCache) -> None:
    """Register analyze_volume_surge tool."""

    @mcp.tool(
        name="analyze_volume_surge",
        annotations={
            "title": "Analyze Volume Surge",
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False
        }
    )
    async def analyze_volume_surge_tool(params: AnalyzeVolumeSurgeInput) -> str:
        """
        Analyze volume surge patterns for a stock.

        This tool calculates volume growth rate by comparing recent trading
        volume to a historical average. It helps identify stocks experiencing
        unusual trading activity.

        Args:
            params: Input parameters including symbol, dates, analysis periods

        Returns:
            JSON-formatted string with volume surge analysis

        Error Handling:
            - Returns "Error: Insufficient data for analysis" if not enough history
            - Returns "Error: Failed to analyze volume surge" if analysis fails
        """
        try:
            # Get data
            if not params.force_refresh:
                df = cache.get_stock_history(
                    params.symbol,
                    params.start_date,
                    params.end_date
                )
            else:
                df = await StockDataFetcher.get_stock_history(
                    params.symbol,
                    params.start_date,
                    params.end_date
                )
                cache.save_stock_history(params.symbol, df)

            if df is None or df.empty:
                return f"Error: No data found for stock {params.symbol}"

            # Analyze
            result = StockAnalyzer.calculate_volume_growth(
                df, params.recent_days, params.compare_period
            )

            if result is None:
                return f"Error: Insufficient data for analysis (need at least {params.recent_days + params.compare_period} days)"

            return json.dumps({
                "symbol": params.symbol,
                "analysis_type": "volume_surge",
                "recent_days": params.recent_days,
                "compare_period": params.compare_period,
                "volume_growth_rate": result['volume_growth_rate'],
                "amount_growth_rate": result['amount_growth_rate'],
                "recent_avg_volume": result['recent_avg_volume'],
                "compare_avg_volume": result['compare_avg_volume'],
                "recent_avg_amount": result['recent_avg_amount'],
                "compare_avg_amount": result['compare_avg_amount']
            }, ensure_ascii=False, indent=2)

        except Exception as e:
            return f"Error: Failed to analyze volume surge: {str(e)}"


def register_analyze_amount_surge(mcp: FastMCP, cache: StockDataCache) -> None:
    """Register analyze_amount_surge tool."""

    @mcp.tool(
        name="analyze_amount_surge",
        annotations={
            "title": "Analyze Trading Amount Surge",
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False
        }
    )
    async def analyze_amount_surge_tool(params: AnalyzeAmountSurgeInput) -> str:
        """
        Analyze trading amount surge patterns for a stock.

        Similar to volume surge analysis but focuses on trading amount
        (成交额) which reflects total money traded rather than just volume.

        Args:
            params: Input parameters including symbol, dates, analysis periods

        Returns:
            JSON-formatted string with amount surge analysis
        """
        try:
            # Get data
            if not params.force_refresh:
                df = cache.get_stock_history(
                    params.symbol,
                    params.start_date,
                    params.end_date
                )
            else:
                df = await StockDataFetcher.get_stock_history(
                    params.symbol,
                    params.start_date,
                    params.end_date
                )
                cache.save_stock_history(params.symbol, df)

            if df is None or df.empty:
                return f"Error: No data found for stock {params.symbol}"

            # Analyze
            result = StockAnalyzer.calculate_amount_growth(
                df, params.recent_days, params.compare_period
            )

            if result is None:
                return f"Error: Insufficient data for analysis"

            return json.dumps({
                "symbol": params.symbol,
                "analysis_type": "amount_surge",
                "recent_days": params.recent_days,
                "compare_period": params.compare_period,
                "volume_growth_rate": result['volume_growth_rate'],
                "amount_growth_rate": result['amount_growth_rate']
            }, ensure_ascii=False, indent=2)

        except Exception as e:
            return f"Error: Failed to analyze amount surge: {str(e)}"


def register_screen_stocks(mcp: FastMCP, cache: StockDataCache) -> None:
    """Register screen_stocks tool."""

    @mcp.tool(
        name="screen_stocks",
        annotations={
            "title": "Screen Stocks by Criteria",
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False
        }
    )
    async def screen_stocks_tool(params: ScreenStocksInput) -> str:
        """
        Screen stocks based on volume or amount surge criteria.

        This tool analyzes multiple stocks and returns those meeting the
        specified growth threshold. Useful for finding active stocks with
        unusual trading patterns.

        Args:
            params: Input parameters including dates, criteria, thresholds

        Returns:
            JSON-formatted string with screening results

        Error Handling:
            - Returns error message if stock list cannot be fetched
            - Limits results to avoid overwhelming responses
        """
        try:
            # Get stock list
            stock_list_df = cache.get_stock_list()
            if stock_list_df is None or stock_list_df.empty:
                stock_list_df = await StockDataFetcher.get_all_stocks_list()
                cache.save_stock_list(stock_list_df)

            # Get symbols
            symbols = stock_list_df['symbol'].tolist()

            results = []
            checked_count = 0

            # Analyze each stock
            for symbol in symbols:
                checked_count += 1

                # Limit to avoid excessive processing
                if checked_count > 200:
                    break

                try:
                    # Get data
                    df = cache.get_stock_history(
                        symbol,
                        params.start_date,
                        params.end_date
                    )

                    if df is None or len(df) < params.recent_days + params.compare_period:
                        continue

                    # Analyze
                    result = StockAnalyzer.calculate_volume_growth(
                        df, params.recent_days, params.compare_period
                    )

                    if result is None:
                        continue

                    # Check threshold
                    growth_rate = result['amount_growth_rate'] if params.criterion == 'amount_surge' else result['volume_growth_rate']

                    if growth_rate >= params.threshold:
                        stock_info = stock_list_df[stock_list_df['symbol'] == symbol].iloc[0] if not stock_list_df[
                            stock_list_df['symbol'] == symbol].empty else {}

                        results.append({
                            "symbol": symbol,
                            "name": stock_info.get('name', 'Unknown'),
                            "volume_growth_rate": result['volume_growth_rate'],
                            "amount_growth_rate": result['amount_growth_rate'],
                            "recent_avg_volume": result['recent_avg_volume'],
                            "recent_avg_amount": result['recent_avg_amount']
                        })

                except Exception:
                    continue

            # Sort and limit
            results.sort(
                key=lambda x: x['amount_growth_rate'] if params.criterion == 'amount_surge' else x['volume_growth_rate'],
                reverse=True
            )
            results = results[:params.limit]

            return json.dumps({
                "criterion": params.criterion,
                "threshold": params.threshold,
                "recent_days": params.recent_days,
                "compare_period": params.compare_period,
                "total_checked": checked_count,
                "matching_stocks": len(results),
                "results": results
            }, ensure_ascii=False, indent=2)

        except Exception as e:
            return f"Error: Failed to screen stocks: {str(e)}"


def register_update_cache(mcp: FastMCP, cache: StockDataCache) -> None:
    """Register update_cache tool."""

    @mcp.tool(
        name="update_cache",
        annotations={
            "title": "Update Stock Data Cache",
            "readOnlyHint": False,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False
        }
    )
    async def update_cache_tool(params: UpdateCacheInput) -> str:
        """
        Update local cache with fresh stock data.

        This tool fetches latest stock data from AKShare and updates
        the local SQLite cache. Use this periodically to ensure you
        have the most recent data.

        Args:
            params: Input parameters including optional symbol list and date range

        Returns:
            JSON-formatted string with update results

        Error Handling:
            - Returns error message if fetch fails
            - Reports success/failure for each symbol
        """
        try:
            # Determine symbols to update
            if params.symbols:
                symbols = [s.strip() for s in params.symbols.split(',')]
            else:
                stock_list_df = cache.get_stock_list()
                if stock_list_df is None or stock_list_df.empty:
                    stock_list_df = await StockDataFetcher.get_all_stocks_list()
                    cache.save_stock_list(stock_list_df)
                symbols = stock_list_df['symbol'].tolist()[:50]  # Limit to 50 for initial update

            # Update each symbol
            results = {
                "total": len(symbols),
                "success": 0,
                "failed": 0,
                "failures": []
            }

            for symbol in symbols:
                try:
                    df = await StockDataFetcher.get_stock_history(
                        symbol,
                        params.start_date,
                        params.end_date
                    )
                    cache.save_stock_history(symbol, df)
                    results['success'] += 1
                except Exception as e:
                    results['failed'] += 1
                    results['failures'].append({
                        "symbol": symbol,
                        "error": str(e)
                    })

            return json.dumps(results, ensure_ascii=False, indent=2)

        except Exception as e:
            return f"Error: Failed to update cache: {str(e)}"


def register_get_cache_status(mcp: FastMCP, cache: StockDataCache) -> None:
    """Register get_cache_status tool."""

    @mcp.tool(
        name="get_cache_status",
        annotations={
            "title": "Get Cache Status",
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False
        }
    )
    async def get_cache_status_tool(params: GetCacheStatusInput) -> str:
        """
        Get current cache status and statistics.

        This tool returns information about the local data cache including
        number of cached stocks, date ranges, and database size.

        Args:
            params: Input parameters with optional detailed flag

        Returns:
            JSON-formatted string with cache statistics
        """
        try:
            stats = cache.get_cache_stats()

            if params.detailed:
                return json.dumps(stats, ensure_ascii=False, indent=2)
            else:
                return json.dumps({
                    "cached_stocks": stats['cached_stocks'],
                    "stock_list_count": stats['stock_list_count']
                }, ensure_ascii=False, indent=2)

        except Exception as e:
            return f"Error: Failed to get cache status: {str(e)}"
