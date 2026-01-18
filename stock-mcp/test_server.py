#!/usr/bin/env python3
"""
Test MCP server initialization without running.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

print("Testing MCP server initialization...")

try:
    from mcp.server.fastmcp import FastMCP
    print("[OK] MCP SDK imported")

    mcp = FastMCP(
        "stock_mcp",
        instructions="Test server"
    )
    print("[OK] FastMCP server initialized")

    # Check if tools can be registered
    from stock_mcp import config
    print("[OK] Config imported")

    from stock_mcp.cache import StockDataCache
    cache = StockDataCache(db_path=config.DB_PATH)
    print("[OK] Cache initialized")

    print("\n[OK] All components initialized successfully!")
    print("\nNote: To run the actual server, use:")
    print("  python server.py")
    print("\nThe server will start and wait for MCP client connections.")

except Exception as e:
    print(f"[FAIL] Error: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
