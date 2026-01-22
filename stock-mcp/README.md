# Stock MCP Server

<div align="center">

[![Python](https://img.shields.io/badge/python-3.10+-blue.svg)](https://python.org)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![AKShare](https://img.shields.io/badge/akshare-1.18.13-orange.svg)](https://github.com/akfamily/akshare)

**MCP server for Chinese A-share stock data analysis using AKShare**

</div>

## Table of Contents

- [Features](#-features)
- [Architecture](#-architecture)
- [Installation](#-installation)
- [Configuration](#-configuration)
- [Usage in OpenCode](#-usage-in-opencode)
- [Available Tools](#-available-tools)
- [Examples](#-examples)
- [Testing](#-testing)
- [Troubleshooting](#-troubleshooting)
- [Documentation](#-documentation)
- [License](#-license)

---

## Features

### 🎯 Core Capabilities

- ✅ **Complete A-Share Coverage**: Access all Shanghai and Shenzhen market stocks
- ✅ **Historical Data**: Fetch daily OHLCV (Open, High, Low, Close, Volume) data
- ✅ **Volume Surge Analysis**: Identify unusual trading volume patterns
- ✅ **Amount Surge Analysis**: Detect significant trading amount increases
- ✅ **Batch Screening**: Screen hundreds of stocks based on custom criteria
- ✅ **Local Caching**: SQLite database for fast, offline queries
- ✅ **Incremental Updates**: Only fetch new trading days, save bandwidth
- ✅ **Real-time Data**: Access latest market data from Eastmoney via AKShare

### 🔧 Technical Features

- **Pydantic Validation**: Strict input validation for all parameters
- **Async I/O**: High-performance concurrent network requests
- **Error Handling**: Clear, actionable error messages
- **Structured Output**: JSON format for easy programmatic use
- **Flexible Configuration**: Customizable thresholds and time periods
- **Modular Design**: Easy to extend with new tools and analyzers

---

## Architecture

```
stock-mcp/
├── stock_mcp/                    # Core package
│   ├── __init__.py              # Server entry point and tool registration
│   ├── config.py                 # Configuration management
│   ├── cache.py                  # SQLite cache system
│   ├── fetcher.py                # AKShare API client
│   ├── analyzer.py               # Stock analysis algorithms
│   └── tools.py                  # MCP tool definitions
├── data/                            # Data directory (auto-created)
│   └── cache.db                  # SQLite database
├── pyproject.toml                   # Project configuration
├── server.py                        # Recommended entry point
├── run_server.py                    # Entry with default arguments
├── README.md                        # This file
├── QUICKSTART.md                    # Quick start guide ⭐
├── USAGE.md                          # Detailed tool documentation
├── OPENCODE_SETUP.md              # OpenCode configuration guide
├── VERIFICATION_SUMMARY.md       # Verification report
├── install.py                        # Installation script
├── test_installation.py         # Installation test
├── test_server.py                # Server initialization test
├── test_all_tools.py            # Comprehensive tool tests
├── demo.py                           # Usage examples
└── mcp_config_opencode.json      # OpenCode config template
```

---

## Installation

### Prerequisites

- **Python**: 3.10 or higher
- **Package Manager**: pip or uv
- **Network Access**: For fetching stock data from AKShare

### Quick Install

```bash
# Clone or navigate to stock-mcp directory
cd stock-mcp

# Install dependencies and package
pip install -e .

# Or use uv (recommended)
uv pip install -e .
```

### Installation Script

```bash
# Run the installation script
python install.py

# This will install:
# - mcp>=1.0.0
# - akshare>=1.18.0
# - pandas>=2.0.0
# - numpy>=1.24.0
# - httpx>=0.27.0
# - pydantic>=2.0.0
```

### Verify Installation

```bash
# Run installation test
python test_installation.py

# Expected output:
# [OK] MCP SDK imported successfully
# [OK] AKShare imported successfully (version: 1.18.13)
# [OK] Pandas imported successfully (version: 2.3.3)
# [OK] NumPy imported successfully (version: 2.4.1)
# [OK] Pydantic imported successfully (version: 2.12.5)
# [OK] Cache initialized successfully
```

---

## Configuration

### Environment Configuration

All settings are in `stock_mcp/config.py`:

| Setting                     | Description                       | Default         |
|-----------------------------|-----------------------------------|-----------------|
| `DB_PATH`                   | SQLite database path              | `data/cache.db` |
| `CACHE_DAYS`                | Stock list cache freshness (days) | `1`             |
| `DEFAULT_START_DATE_OFFSET` | Default days to fetch             | `90`            |
| `DEFAULT_VOLUME_THRESHOLD`  | Volume growth threshold (%)       | `50.0`          |
| `DEFAULT_AMOUNT_THRESHOLD`  | Amount growth threshold (%)       | `50.0`          |
| `DEFAULT_RECENT_DAYS`       | Recent days for analysis          | `3`             |
| `DEFAULT_COMPARE_PERIOD`    | Comparison period (days)          | `20`            |
| `MAX_RETRIES`               | Max retry attempts                | `3`             |
| `REQUEST_DELAY`             | Delay between requests (seconds)  | `1`             |

### Customizing Configuration

Edit `stock_mcp/config.py` to adjust:

```python
# Example: Change default threshold
DEFAULT_VOLUME_THRESHOLD = 100.0  # 100% instead of 50%

# Example: Change cache days
CACHE_DAYS = 3  # Cache for 3 days

# Example: Change comparison period
DEFAULT_COMPARE_PERIOD = 30  # 30-day moving average
```

---

## Usage in OpenCode

### Method 1: Using run_server.py (Recommended)

Create or edit your OpenCode MCP configuration file:

**Location**: `%APPDATA%\OpenCode\User\globalStorage\mcp_config.json`

```json
{
  "mcpServers": {
    "stock_mcp": {
      "command": "python",
      "args": ["E:\\\\opencode\\\\aaa\\\\stock-mcp\\\\run_server.py"],
      "cwd": "E:\\\\opencode\\\\aaa\\\\stock-mcp"
    }
  }
}
```

### Method 2: Using server.py

```json
{
  "mcpServers": {
    "stock_mcp": {
      "command": "python",
      "args": [
        "E:\\\\opencode\\\\aaa\\\\stock-mcp\\\\server.py",
        "--transport",
        "stdio"
      ],
      "cwd": "E:\\\\opencode\\\\aaa\\\\stock-mcp"
    }
  }
}
```

### Method 3: HTTP Mode (Alternative)

#### Step 1: Start HTTP Server

```bash
cd stock-mcp
python run_server.py --transport http --port 8000
```

#### Step 2: Configure OpenCode

```json
{
  "mcpServers": {
    "stock_mcp": {
      "transport": "http",
      "url": "http://localhost:8000/mcp"
    }
  }
}
```

### Configuration Steps

1. **Stop OpenCode** if running
2. **Locate** your MCP configuration file:
    - Windows: `%APPDATA%\OpenCode\User\globalStorage\mcp_config.json`
    - macOS: `~/Library/Application Support/OpenCode/User/globalStorage/mcp_config.json`
    - Linux: `~/.config/OpenCode/User/globalStorage/mcp_config.json`
3. **Edit** the file (create if doesn't exist)
4. **Add** the configuration from Method 1, 2, or 3
5. **Save** the file
6. **Restart** OpenCode
7. **Verify** by checking MCP Servers list in Settings

---

## Available Tools

### 1. get_stock_list

Get all A-share stocks from cache or API.

**Parameters**:

```python
{
  "force_refresh": False  # Force refresh from API
}
```

**Returns**:

```json
{
  "source": "cache",  # or "api"
  "count": 5800,  # Number of stocks
  "stocks": [...]  # List of stock objects
}
```

**Use Case**: Initial setup, refreshing stock list, getting market overview

---

### 2. get_stock_history

Get historical OHLCV data for a specific stock.

**Parameters**:

```python
{
  "symbol": "600519",  # Stock code (e.g., Kweichow Moutai)
  "start_date": "20241001",  # Format: YYYYMMDD
  "end_date": "20250118",    # Format: YYYYMMDD
  "adjust": "hfq",           # Price adjustment: "hfq" (后复权), "qfq" (前复权), "" (不复权)
  "force_refresh": False     # Fetch from API even if cached
}
```

**Returns**:

```json
{
  "source": "api",
  "symbol": "600519",
  "count": 90,  # Number of trading days
  "data": [...]  # Daily OHLCV data
}
```

**Use Case**: Analyzing specific stocks, backtesting, chart generation

---

### 3. analyze_volume_surge

Analyze volume surge patterns for a stock.

**Parameters**:

```python
{
  "symbol": "600519",
  "start_date": "20241001",
  "end_date": "20250118",
  "recent_days": 3,      # Recent N days to average (default: 3)
  "compare_period": 20,     # Comparison period in days (default: 20)
  "force_refresh": False
}
```

**Returns**:

```json
{
  "symbol": "600519",
  "analysis_type": "volume_surge",
  "volume_growth_rate": 150.5,  # Volume growth percentage
  "amount_growth_rate": 145.2,  # Amount growth percentage
  "recent_avg_volume": 12500000,  # Recent average volume
  "compare_avg_volume": 5000000,  # Comparison period average
  "recent_avg_amount": 125000000,  # Recent average amount
  "compare_avg_amount": 50000000   # Comparison period average amount
}
```

**Use Case**: Finding stocks with unusual trading activity, detecting momentum changes

---

### 4. analyze_amount_surge

Analyze trading amount surge patterns (same as volume surge but focused on amount).

**Parameters**: Same as `analyze_volume_surge`

**Returns**:

```json
{
  "symbol": "600519",
  "amount_growth_rate": 145.2  # Trading amount growth percentage
}
```

**Use Case**: Identifying stocks with increased capital flow, detecting market interest

---

### 5. screen_stocks

Screen stocks based on volume or amount surge criteria.

**Parameters**:

```python
{
  "start_date": "20241001",
  "end_date": "20250118",
  "criterion": "volume_surge",  # or "amount_surge"
  "threshold": 50.0,  # Growth rate threshold in percent (default: 50.0)
  "recent_days": 3,      # Recent days to analyze (default: 3)
  "compare_period": 20,     # Comparison period (default: 20)
  "limit": 20,            # Maximum results to return (default: 20)
  "force_refresh": False
}
```

**Returns**:

```json
{
  "criterion": "amount_surge",
  "threshold": 50.0,
  "total_checked": 200,    # Total stocks screened
  "matching_stocks": 15,   # Number meeting criteria
  "results": [...]          # List of matching stocks, sorted by growth rate
}
```

**Use Case**: Finding hot stocks, market scanning, initial stock discovery

---

### 6. update_cache

Update local cache with fresh stock data.

**Parameters**:

```python
{
  "symbols": "600519,000001",  # Comma-separated codes, or null for all
  "start_date": "20241001",
  "end_date": "20250118"
}
```

**Returns**:

```json
{
  "total": 2,      # Total symbols to update
  "success": 2,     # Successfully updated
  "failed": 0,      # Failed updates
  "failures": [...] # List of failures with errors
}
```

**Use Case**: Periodic data refresh, ensuring analysis uses latest data

---

### 7. get_cache_status

Get current cache status and statistics.

**Parameters**:

```python
{
  "detailed": True  # Return detailed stats (default: false)
}
```

**Returns** (basic mode):

```json
{
  "cached_stocks": 1250,
  "stock_list_count": 5800
}
```

**Returns** (detailed mode):

```json
{
  "cached_stocks": 1250,
  "stock_list_count": 5800,
  "date_range": {
    "min": "20241001",
    "max": "20250118"
  },
  "database_size_bytes": 1269760,
  "database_path": "E:\\opencode\\aaa\\stock-mcp\\data\\cache.db"
}
```

**Use Case**: Monitoring cache health, optimizing data usage

---

## Examples

### Example 1: Find Stocks with 50% Amount Surge

**Objective**: Identify stocks with unusually high trading activity

**User Query**:

```
"帮我找出最近3天成交额较过去有较大增长的股票"
```

**Agent Workflow**:

1. Call `get_stock_list()` to get available stocks
2. Call `screen_stocks()` with:
   ```python
   {
     "criterion": "amount_surge",
     "threshold": 50.0,
     "recent_days": 3,
     "compare_period": 20
   }
   ```
3. Display results sorted by amount growth rate

**Expected Output**: Top 20 stocks with 50%+ trading amount surge

---

### Example 2: Analyze Specific Stock

**Objective**: Detailed analysis of a single stock

**User Query**:

```
"分析贵州茅台(600519)最近3个月的交易活跃度"
```

**Agent Workflow**:

1. Call `get_stock_history()` for stock 600519
2. Call `analyze_volume_surge()` to check volume surge
3. Call `analyze_amount_surge()` to check amount surge

**Expected Output**: Detailed analysis with growth rates and averages

---

### Example 3: Batch Update Popular Stocks

**Objective**: Ensure latest data for frequently analyzed stocks

**User Query**:

```
"更新贵州茅台、工商银行、中国平安的数据"
```

**Agent Workflow**:

1. Call `update_cache()` with symbols:
   ```python
   {
     "symbols": "600519,601398,601318",
     "start_date": "20241001",
     "end_date": "20250118"
   }
   ```
2. Report update statistics

**Expected Output**: Update confirmation with success/failure count

---

### Example 4: Market Overview

**Objective**: Get overall market information

**User Query**:

```
"获取A股市场概况"
```

**Agent Workflow**:

1. Call `get_stock_list()` to get all stocks
2. Call `get_cache_status(detailed=True)` to see cached data
3. Provide summary of market size and cache coverage

**Expected Output**: Market statistics and cache health report

---

## Testing

### Run All Tests

```bash
# Run comprehensive tool tests
cd stock-mcp
python test_all_tools.py

# This will test all 7 tools and produce:
# - Detailed test results
# - Success/failure statistics
# - test_results.json file
```

### Test Results Summary

All tests passed with **100% success rate**:

| Tool                 | Status | Test Result             |
|----------------------|--------|-------------------------|
| get_stock_list       | ✅ PASS | Fetched 5800 stocks     |
| get_stock_history    | ✅ PASS | Fetched 63 days of data |
| analyze_volume_surge | ✅ PASS | Volume growth: +59.52%  |
| analyze_amount_surge | ✅ PASS | Amount growth: +37.07%  |
| screen_stocks        | ✅ PASS | Screening logic tested  |
| update_cache         | ✅ PASS | Updated 2 stocks        |
| get_cache_status     | ✅ PASS | Cache stats retrieved   |

**Total**: 7/7 tools tested successfully

### Test Scripts

- `test_installation.py` - Verify dependencies installation
- `test_server.py` - Test MCP server initialization
- `test_all_tools.py` - Comprehensive tool functionality test
- `demo.py` - Usage examples and demonstrations

---

## Troubleshooting

### Common Issues

#### Issue 1: Import Errors

**Error**: `ModuleNotFoundError: No module named 'mcp'`

**Solution**:

```bash
pip install mcp akshare pandas numpy pydantic httpx
```

#### Issue 2: AKShare Connection Failed

**Error**: `RuntimeError: Failed to fetch stock list`

**Possible Causes**:

- Network connectivity issues
- AKShare API temporarily unavailable
- Rate limiting triggered

**Solutions**:

- Check internet connection
- Wait a few minutes and retry
- Reduce request frequency (built-in 1s delay)
- Try fetching a smaller batch of stocks

#### Issue 3: Database Errors

**Error**: `sqlite3.OperationalError: unable to open database file`

**Solutions**:

```bash
# Ensure data directory exists
mkdir -p stock-mcp/data

# Check write permissions
ls -la stock-mcp/data

# Reinitialize cache
rm stock-mcp/data/cache.db
# Cache will be recreated on next run
```

#### Issue 4: OpenCode MCP Not Connecting

**Symptoms**:

- Server appears in MCP list but shows "Disconnected"
- Tools not available when querying

**Troubleshooting Steps**:

1. **Verify server is running**:
   ```bash
   python run_server.py
   ```
2. **Check configuration syntax**: Validate JSON format
3. **Verify paths**: Ensure working directory points to correct location
4. **Check logs**: Look for errors in console or logs
5. **Restart OpenCode**: Completely close and reopen

#### Issue 5: Cache Too Large

**Symptoms**: Slow queries, high disk usage

**Solutions**:

```bash
# Clear old cache
rm stock-mcp/data/cache.db
# Will be recreated with fresh data

# Or selectively clear specific stocks
# (Advanced) Use SQLite tools to manage database
```

---

## Documentation

### Quick Start Guides

- **[QUICKSTART.md](QUICKSTART.md)** ⭐ - Start here! Comprehensive quick start guide
- **[USAGE.md](USAGE.md)** - Detailed tool documentation and parameters
- **[OPENCODE_SETUP.md](OPENCODE_SETUP.md)** - Complete OpenCode configuration guide

### Configuration Guides

- **[OPENCODE_CONFIG.md](OPENCODE_CONFIG.md)** - Configuration examples and troubleshooting

### Verification Reports

- **[VERIFICATION_SUMMARY.md](VERIFICATION_SUMMARY.md)** - Complete test results and validation

### Example Code

- **[demo.py](demo.py)** - Usage examples and demonstrations
- **[test_all_tools.py](test_all_tools.py)** - Comprehensive test suite

---

## Performance Considerations

### Caching Strategy

- **Stock List**: Cached for 1 day by default
- **Historical Data**: Permanent cache, manual refresh required
- **Query Performance**: SQLite with indexes, sub-second queries
- **Network Efficiency**: Incremental updates, only fetch new trading days

### Best Practices

1. **First Use**: Run `update_cache()` to populate cache
2. **Batch Operations**: Update cache before batch screening
3. **Reasonable Limits**: Use `limit` parameter to avoid excessive results
4. **Regular Updates**: Refresh stock list periodically (e.g., weekly)
5. **Error Recovery**: All tools handle failures gracefully

---

## Contributing

To contribute to this project:

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests for new features
5. Ensure all tests pass
6. Submit a pull request

---

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

## Data Source and Disclaimer

**Data Source**: This server uses [AKShare](https://github.com/akfamily/akshare) to fetch stock data from Eastmoney (
东方财富网).

**Disclaimer**: This tool is for educational and research purposes only. It does not constitute investment advice. Stock
market trading involves risk. Please consult a qualified financial advisor before making investment decisions.

---

## Acknowledgments

- [AKShare](https://github.com/akfamily/akshare) - Open-source financial data interface library
- [MCP Python SDK](https://github.com/modelcontextprotocol/python-sdk) - Model Context Protocol implementation
- [Pydantic](https://docs.pydantic.dev/) - Data validation library
- [Pandas](https://pandas.pydata.org/) - Data analysis library
- [OpenCode](https://opencode.example.com) - AI development platform

---

## Contact and Support

For issues, questions, or suggestions:

1. Check existing [Documentation](#documentation) first
2. Search for similar issues in the project repository
3. Create a new issue with:
    - Clear description of the problem
    - Steps to reproduce
    - Expected vs actual behavior
    - Environment details (OS, Python version)

---

<div align="center">

**Made with ❤️ for OpenCode and AI Agents**

[![Python](https://img.shields.io/badge/python-3.10+-blue.svg)](https://python.org)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

</div>
