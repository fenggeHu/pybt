"""
Quick demo of stock-mcp usage.
"""

import asyncio
import json
from datetime import datetime, timedelta

# Calculate dates
end_date = datetime.now()
start_date_90days = end_date - timedelta(days=90)

# Format dates for AKShare
end_date_str = end_date.strftime('%Y%m%d')
start_date_str = start_date_90days.strftime('%Y%m%d')


async def demo_usage():
    """Demonstrate stock-mcp usage."""
    print("=" * 70)
    print("Stock MCP Server - Usage Demo")
    print("=" * 70)
    print()

    # Note: This is a demonstration of how to use the tools.
    # In OpenCode, you would call these tools through the MCP interface.

    print("Example 1: Get stock list")
    print("-" * 70)
    print("Tool: get_stock_list")
    print("Parameters:")
    print(json.dumps({"force_refresh": False}, indent=2))
    print()
    print("This will return a list of all A-share stocks.")
    print()

    print("\nExample 2: Get history for specific stock")
    print("-" * 70)
    print("Tool: get_stock_history")
    print("Parameters:")
    print(json.dumps({
        "symbol": "600519",
        "start_date": start_date_str,
        "end_date": end_date_str,
        "adjust": "hfq"
    }, indent=2))
    print()
    print("This will return 90 days of historical data for Kweichow Moutai (600519).")
    print()

    print("\nExample 3: Analyze volume surge")
    print("-" * 70)
    print("Tool: analyze_volume_surge")
    print("Parameters:")
    print(json.dumps({
        "symbol": "600519",
        "start_date": start_date_str,
        "end_date": end_date_str,
        "recent_days": 3,
        "compare_period": 20
    }, indent=2))
    print()
    print("This will analyze if volume has surged in the last 3 days compared to the 20-day average.")
    print()

    print("\nExample 4: Screen stocks by amount surge")
    print("-" * 70)
    print("Tool: screen_stocks")
    print("Parameters:")
    print(json.dumps({
        "start_date": start_date_str,
        "end_date": end_date_str,
        "criterion": "amount_surge",
        "threshold": 50.0,
        "recent_days": 3,
        "compare_period": 20,
        "limit": 10
    }, indent=2))
    print()
    print("This will find top 10 stocks with 50%+ trading amount surge.")
    print()

    print("\nExample 5: Update cache")
    print("-" * 70)
    print("Tool: update_cache")
    print("Parameters:")
    print(json.dumps({
        "symbols": "600519,000001,600036",
        "start_date": start_date_str,
        "end_date": end_date_str
    }, indent=2))
    print()
    print("This will update cache for specific stocks with latest data.")
    print()

    print("\nExample 6: Get cache status")
    print("-" * 70)
    print("Tool: get_cache_status")
    print("Parameters:")
    print(json.dumps({"detailed": True}, indent=2))
    print()
    print("This will show cache statistics including size and date range.")
    print()

    print("=" * 70)
    print("End of Demo")
    print("=" * 70)
    print()
    print("To use these tools:")
    print("1. Configure stock-mcp in OpenCode MCP settings")
    print("2. Start OpenCode")
    print("3. Use the tools through the MCP interface")
    print()


if __name__ == "__main__":
    asyncio.run(demo_usage())
