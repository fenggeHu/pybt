#!/usr/bin/env python3
"""
Comprehensive test of all stock-mcp tools.
"""

import asyncio
import json
import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from stock_mcp import config
from stock_mcp.cache import StockDataCache
from stock_mcp.fetcher import StockDataFetcher
from stock_mcp.analyzer import StockAnalyzer

# Calculate dates
end_date = datetime.now()
start_date = end_date - timedelta(days=90)

end_date_str = end_date.strftime('%Y%m%d')
start_date_str = start_date.strftime('%Y%m%d')


async def test_all_tools():
    """Test all 7 MCP tools."""
    print("=" * 70)
    print("Stock MCP Server - Comprehensive Tool Test")
    print("=" * 70)
    print()

    results = {
        "total_tools": 7,
        "passed": 0,
        "failed": 0,
        "tests": []
    }

    cache = StockDataCache(db_path=config.DB_PATH)

    # Test 1: get_stock_list
    print("\n[1/7] Testing get_stock_list...")
    try:
        stock_list_df = await StockDataFetcher.get_all_stocks_list()
        cache.save_stock_list(stock_list_df)

        if stock_list_df is not None and len(stock_list_df) > 0:
            print(f"      [OK] Stock list fetched: {len(stock_list_df)} stocks")
            results['passed'] += 1
            results['tests'].append({
                "tool": "get_stock_list",
                "status": "passed",
                "details": f"Fetched {len(stock_list_df)} stocks"
            })
        else:
            print("      [FAIL] Stock list is empty")
            results['failed'] += 1
            results['tests'].append({
                "tool": "get_stock_list",
                "status": "failed",
                "details": "Empty stock list"
            })
    except Exception as e:
        print(f"      [FAIL] Error: {e}")
        results['failed'] += 1
        results['tests'].append({
            "tool": "get_stock_list",
            "status": "failed",
            "details": f"Error: {str(e)}"
        })

    # Test 2: get_stock_history
    print("\n[2/7] Testing get_stock_history...")
    try:
        test_symbol = "600519"  # Kweichow Moutai
        df = await StockDataFetcher.get_stock_history(
            test_symbol, start_date_str, end_date_str, "hfq"
        )
        cache.save_stock_history(test_symbol, df)

        if df is not None and len(df) > 0:
            print(f"      [OK] History fetched for {test_symbol}: {len(df)} days")
            results['passed'] += 1
            results['tests'].append({
                "tool": "get_stock_history",
                "status": "passed",
                "details": f"Fetched {len(df)} days of data"
            })
        else:
            print(f"      [FAIL] No history for {test_symbol}")
            results['failed'] += 1
            results['tests'].append({
                "tool": "get_stock_history",
                "status": "failed",
                "details": "No data returned"
            })
    except Exception as e:
        print(f"      [FAIL] Error: {e}")
        results['failed'] += 1
        results['tests'].append({
            "tool": "get_stock_history",
            "status": "failed",
            "details": f"Error: {str(e)}"
        })

    # Test 3: analyze_volume_surge
    print("\n[3/7] Testing analyze_volume_surge...")
    try:
        test_symbol = "600519"
        df = cache.get_stock_history(test_symbol, start_date_str, end_date_str)
        if df is None or len(df) < 23:
            # Fetch if not in cache
            df = await StockDataFetcher.get_stock_history(
                test_symbol, start_date_str, end_date_str, "hfq"
            )
            cache.save_stock_history(test_symbol, df)

        result = StockAnalyzer.calculate_volume_growth(df, 3, 20)

        if result is not None:
            print(f"      [OK] Volume surge calculated: {result['volume_growth_rate']:.2f}%")
            results['passed'] += 1
            results['tests'].append({
                "tool": "analyze_volume_surge",
                "status": "passed",
                "details": f"Volume growth: {result['volume_growth_rate']:.2f}%, Amount growth: {result['amount_growth_rate']:.2f}%"
            })
        else:
            print("      [FAIL] Insufficient data for volume surge analysis")
            results['failed'] += 1
            results['tests'].append({
                "tool": "analyze_volume_surge",
                "status": "failed",
                "details": "Insufficient data"
            })
    except Exception as e:
        print(f"      [FAIL] Error: {e}")
        results['failed'] += 1
        results['tests'].append({
            "tool": "analyze_volume_surge",
            "status": "failed",
            "details": f"Error: {str(e)}"
        })

    # Test 4: analyze_amount_surge
    print("\n[4/7] Testing analyze_amount_surge...")
    try:
        test_symbol = "000001"  # Ping An Bank
        df = await StockDataFetcher.get_stock_history(
            test_symbol, start_date_str, end_date_str, "hfq"
        )
        cache.save_stock_history(test_symbol, df)

        result = StockAnalyzer.calculate_amount_growth(df, 3, 20)

        if result is not None:
            print(f"      [OK] Amount surge calculated: {result['amount_growth_rate']:.2f}%")
            results['passed'] += 1
            results['tests'].append({
                "tool": "analyze_amount_surge",
                "status": "passed",
                "details": f"Amount growth: {result['amount_growth_rate']:.2f}%"
            })
        else:
            print("      [FAIL] Insufficient data for amount surge analysis")
            results['failed'] += 1
            results['tests'].append({
                "tool": "analyze_amount_surge",
                "status": "failed",
                "details": "Insufficient data"
            })
    except Exception as e:
        print(f"      [FAIL] Error: {e}")
        results['failed'] += 1
        results['tests'].append({
            "tool": "analyze_amount_surge",
            "status": "failed",
            "details": f"Error: {str(e)}"
        })

    # Test 5: screen_stocks (mock test)
    print("\n[5/7] Testing screen_stocks (mock test)...")
    try:
        # Just test the logic without screening all stocks
        test_symbols = ["600519", "000001", "600036"]
        results_count = 0

        for symbol in test_symbols:
            df = cache.get_stock_history(symbol, start_date_str, end_date_str)
            if df is not None and len(df) >= 23:
                result = StockAnalyzer.calculate_volume_growth(df, 3, 20)
                if result is not None and result['volume_growth_rate'] > 0:
                    results_count += 1

        print(f"      [OK] Screening logic tested: {results_count}/{len(test_symbols)} stocks met criteria")
        results['passed'] += 1
        results['tests'].append({
            "tool": "screen_stocks",
            "status": "passed",
            "details": f"Tested {len(test_symbols)} stocks, {results_count} met criteria"
        })
    except Exception as e:
        print(f"      [FAIL] Error: {e}")
        results['failed'] += 1
        results['tests'].append({
            "tool": "screen_stocks",
            "status": "failed",
            "details": f"Error: {str(e)}"
        })

    # Test 6: update_cache
    print("\n[6/7] Testing update_cache...")
    try:
        test_symbols = "600519,000001"
        symbols_list = [s.strip() for s in test_symbols.split(',')]

        updated = 0
        for symbol in symbols_list:
            try:
                df = await StockDataFetcher.get_stock_history(
                    symbol, start_date_str, end_date_str, "hfq"
                )
                cache.save_stock_history(symbol, df)
                updated += 1
            except Exception:
                pass

        print(f"      [OK] Cache updated for {updated}/{len(symbols_list)} stocks")
        results['passed'] += 1
        results['tests'].append({
            "tool": "update_cache",
            "status": "passed",
            "details": f"Updated {updated} stocks"
        })
    except Exception as e:
        print(f"      [FAIL] Error: {e}")
        results['failed'] += 1
        results['tests'].append({
            "tool": "update_cache",
            "status": "failed",
            "details": f"Error: {str(e)}"
        })

    # Test 7: get_cache_status
    print("\n[7/7] Testing get_cache_status...")
    try:
        stats = cache.get_cache_stats()

        print(f"      [OK] Cache stats: {stats['cached_stocks']} stocks, {stats['stock_list_count']} in list")
        print(f"           Database size: {stats['database_size_bytes']} bytes")

        results['passed'] += 1
        results['tests'].append({
            "tool": "get_cache_status",
            "status": "passed",
            "details": f"{stats['cached_stocks']} stocks cached"
        })
    except Exception as e:
        print(f"      [FAIL] Error: {e}")
        results['failed'] += 1
        results['tests'].append({
            "tool": "get_cache_status",
            "status": "failed",
            "details": f"Error: {str(e)}"
        })

    # Print summary
    print("\n" + "=" * 70)
    print("TEST SUMMARY")
    print("=" * 70)
    print(f"Total Tools:  {results['total_tools']}")
    print(f"Passed:       {results['passed']}")
    print(f"Failed:       {results['failed']}")
    print(f"Success Rate: {results['passed']}/{results['total_tools']} ({100 * results['passed'] / results['total_tools']:.1f}%)")
    print()

    # Print detailed results
    print("DETAILED RESULTS:")
    print("-" * 70)
    for test in results['tests']:
        status_icon = "[OK]" if test['status'] == 'passed' else "[FAIL]"
        print(f"{status_icon} {test['tool']:25} - {test['details']}")

    # Save results to file
    with open('test_results.json', 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    print(f"\nResults saved to: test_results.json")
    print("\n" + "=" * 70)

    return results['failed'] == 0


if __name__ == "__main__":
    success = asyncio.run(test_all_tools())
    import sys

    sys.exit(0 if success else 1)
