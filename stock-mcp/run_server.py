#!/usr/bin/env python3
"""
MCP server entry point that works with stdio transport.
"""

import os
import sys

# Get current directory
current_dir = os.path.dirname(os.path.abspath(__file__))

# Add to path
sys.path.insert(0, current_dir)

# Import server
from stock_mcp import main

# Add stdio transport argument if not present
if "--transport" not in sys.argv:
    sys.argv.append("--transport")
    sys.argv.append("stdio")

# Run
if __name__ == "__main__":
    main()
