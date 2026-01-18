"""
Stock MCP Server

MCP server for Chinese A-share stock data analysis using AKShare.
"""

from mcp.server.fastmcp import FastMCP

from stock_mcp import config
from stock_mcp.tools import (
    register_get_stock_list,
    register_get_stock_history,
    register_analyze_volume_surge,
    register_analyze_amount_surge,
    register_screen_stocks,
    register_update_cache,
    register_get_cache_status,
)
from stock_mcp.cache import StockDataCache

# Initialize MCP server
mcp = FastMCP(
    "stock_mcp",
    instructions=(
        "This server provides tools for analyzing Chinese A-share stocks using AKShare data. "
        "It can fetch stock data, analyze trading patterns, and screen stocks based on "
        "various criteria like volume surge, trading amount growth, etc. "
        "Data is cached locally in SQLite for better performance."
    ),
)

# Initialize cache
cache = StockDataCache(db_path=config.DB_PATH)

# Register all tools
register_get_stock_list(mcp, cache)
register_get_stock_history(mcp, cache)
register_analyze_volume_surge(mcp, cache)
register_analyze_amount_surge(mcp, cache)
register_screen_stocks(mcp, cache)
register_update_cache(mcp, cache)
register_get_cache_status(mcp, cache)


def main():
    """Entry point for running MCP server."""
    import sys

    # Parse command line arguments
    transport = "stdio"
    port = 8000

    for arg in sys.argv[1:]:
        if arg == "--transport" and sys.argv.index(arg) + 1 < len(sys.argv):
            transport = sys.argv[sys.argv.index(arg) + 1]
        elif arg == "--port" and sys.argv.index(arg) + 1 < len(sys.argv):
            port = int(sys.argv[sys.argv.index(arg) + 1])

    # Run server
    if transport == "http":
        mcp.run(transport="streamable-http", port=port)
    else:
        mcp.run()


if __name__ == "__main__":
    main()
