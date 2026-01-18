"""
Test script to verify stock-mcp installation.
"""

import sys
import asyncio
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))


async def test_imports():
    """Test if all imports work."""
    print("Testing imports...")

    try:
        from mcp.server.fastmcp import FastMCP
        print("[OK] MCP SDK imported successfully")
    except ImportError as e:
        print(f"[FAIL] MCP SDK import failed: {e}")
        return False

    try:
        import akshare as ak
        print(f"[OK] AKShare imported successfully (version: {ak.__version__})")
    except ImportError as e:
        print(f"[FAIL] AKShare import failed: {e}")
        return False

    try:
        import pandas as pd
        print(f"[OK] Pandas imported successfully (version: {pd.__version__})")
    except ImportError as e:
        print(f"[FAIL] Pandas import failed: {e}")
        return False

    try:
        import numpy as np
        print(f"[OK] NumPy imported successfully (version: {np.__version__})")
    except ImportError as e:
        print(f"[FAIL] NumPy import failed: {e}")
        return False

    try:
        import pydantic
        print(f"[OK] Pydantic imported successfully (version: {pydantic.__version__})")
    except ImportError as e:
        print(f"[FAIL] Pydantic import failed: {e}")
        return False

    return True


async def test_basic_functionality():
    """Test basic functionality."""
    print("\nTesting basic functionality...")

    try:
        # Test cache initialization
        from stock_mcp.cache import StockDataCache
        cache = StockDataCache(db_path="test_cache.db")
        print("[OK] Cache initialized successfully")

        # Test stats
        stats = cache.get_cache_stats()
        print(f"[OK] Cache stats retrieved: {stats['cached_stocks']} stocks cached")

        # Cleanup test database
        import os
        if os.path.exists("test_cache.db"):
            os.remove("test_cache.db")
            print("[OK] Test database cleaned up")

    except Exception as e:
        print(f"[FAIL] Basic functionality test failed: {e}")
        return False

    return True


async def test_akshare_connection():
    """Test AKShare API connection."""
    print("\nTesting AKShare API connection...")

    try:
        import akshare as ak

        # Try to get a small sample
        print("Fetching stock list sample...")
        df = ak.stock_zh_a_spot_em()

        if df is not None and len(df) > 0:
            print(f"[OK] AKShare API connected successfully")
            print(f"  Sample stock: {df.iloc[0]['代码']} - {df.iloc[0]['名称']}")
            return True
        else:
            print("[FAIL] AKShare returned empty data")
            return False

    except Exception as e:
        print(f"[FAIL] AKShare connection failed: {e}")
        return False


async def main():
    """Run all tests."""
    print("=" * 60)
    print("Stock MCP Server - Installation Test")
    print("=" * 60)

    # Test imports
    if not await test_imports():
        print("\n[X] Import tests failed. Please install dependencies:")
        print("   pip install mcp akshare pandas numpy pydantic httpx")
        return False

    # Test basic functionality
    if not await test_basic_functionality():
        print("\n[X] Basic functionality tests failed")
        return False

    # Test AKShare connection (optional, may fail due to network)
    await test_akshare_connection()

    print("\n" + "=" * 60)
    print("[OK] Installation test completed!")
    print("=" * 60)
    print("\nYou can now run the server with:")
    print("  python -m stock_mcp")
    print("\nOr with HTTP mode:")
    print("  python -m stock_mcp --transport http --port 8000")

    return True


if __name__ == "__main__":
    result = asyncio.run(main())
    sys.exit(0 if result else 1)
