# OpenCode MCP Configuration Example

This is an example configuration for adding stock-mcp to OpenCode.

## Using stdio (Recommended for local use)

```json
{
  "mcpServers": {
    "stock_mcp": {
      "command": "python",
      "args": ["-m", "stock_mcp"],
      "cwd": "E:\\opencode\\aaa\\stock-mcp"
    }
  }
}
```

## Using HTTP (For remote access)

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

## Configuration Options

### stdio Mode

- `command`: Python executable path
- `args`: Arguments to pass (use `-m stock_mcp`)
- `cwd`: Working directory (path to stock-mcp folder)

### HTTP Mode

- `transport`: Must be "http"
- `url`: Server URL (http://localhost:8000/mcp)
- `port`: Port number (must match server --port argument)

## Location

This file should be placed in your OpenCode configuration directory:

- Windows: `%APPDATA%\OpenCode\User\globalStorage\mcp_config.json`
- macOS: `~/Library/Application Support/OpenCode/User/globalStorage/mcp_config.json`
- Linux: `~/.config/OpenCode/User/globalStorage/mcp_config.json`

## Notes

1. Make sure to adjust paths based on your installation location
2. The `cwd` option in stdio mode is important for the server to find its modules
3. Test your configuration by restarting OpenCode after making changes
4. You can verify the connection by checking the MCP server list in OpenCode
