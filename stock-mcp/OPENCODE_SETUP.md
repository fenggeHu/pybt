# Stock MCP Server - OpenCode Configuration Guide

## Configuration File

The MCP configuration file has been created at:
```
stock-mcp/mcp_config_opencode.json
```

## Installation Instructions

### Option 1: Using stdio (Recommended)

Copy the content of `mcp_config_opencode.json` and add it to your OpenCode MCP configuration file.

**OpenCode MCP Config Location:**
- Windows: `%APPDATA%\OpenCode\User\globalStorage\mcp_config.json`
- Example: `C:\Users\YourName\AppData\Roaming\OpenCode\User\globalStorage\mcp_config.json`

### Option 2: Manual Edit

1. Open OpenCode
2. Go to Settings > MCP Servers
3. Click "Add Server"
4. Enter the following configuration:

**Server Name:** `stock_mcp`

**Command:** `python`

**Arguments:** (use the args from mcp_config_opencode.json)

**Working Directory:** `E:\opencode\aaa\stock-mcp`

### Option 3: Using HTTP Mode (Alternative)

If you prefer HTTP mode:

1. Start the server in HTTP mode:
   ```bash
   cd stock-mcp
   python server.py --transport http --port 8000
   ```

2. Add server configuration:
   ```json
   {
     "stock_mcp": {
       "transport": "http",
       "url": "http://localhost:8000/mcp"
     }
   }
   ```

## Verification

After configuration:

1. Restart OpenCode
2. Check MCP Server list in Settings
3. You should see "stock_mcp" in the list
4. The server should show "Connected" status

## Testing

Once configured, you can test by asking any question that requires stock analysis:

Examples:
- "帮我看贵州茅台最近3个月的成交量变化"
- "筛选成交额激增超过50%的股票"
- "分析600519和000001的交易活跃度对比"

## Troubleshooting

### Server won't start

**Check:**
1. Python is in your PATH
2. All dependencies are installed
3. Working directory path is correct
4. Database directory has write permissions

**Fix:**
- Run `python test_server.py` to test initialization
- Check `stock-mcp/data` directory exists
- Ensure `stock_mcp/config.py` DB_PATH is correct

### Tools not appearing

**Check:**
1. MCP configuration file syntax is valid JSON
2. Server name matches exactly ("stock_mcp")
3. Working directory points to correct path

**Fix:**
- Validate JSON with online tool like jsonlint.com
- Restart OpenCode completely
- Check OpenCode logs for errors

### Import errors

If you see import errors in OpenCode MCP logs:

**Possible causes:**
- Dependencies not installed in Python environment
- Path issues with module imports

**Fix:**
```bash
cd stock-mcp
pip install -e .
python test_server.py
```

## Alternative: Direct Command Line

If MCP integration doesn't work, you can still use the tools directly:

```bash
cd stock-mcp
python -c "from stock_mcp import *; from stock_mcp.cache import StockDataCache; cache = StockDataCache(); print(cache.get_cache_stats())"
```

## Next Steps

1. Copy configuration to OpenCode MCP settings
2. Restart OpenCode
3. Test with a simple stock query
4. Review available tools in OpenCode MCP UI
5. Start using stock analysis capabilities!

For more information, see:
- `QUICKSTART.md` - Quick start guide
- `USAGE.md` - Detailed tool documentation
