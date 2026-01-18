#!/usr/bin/env python3
"""
Stock MCP Server Entry Point
"""

import sys
from pathlib import Path

# Add stock_mcp to path
sys.path.insert(0, str(Path(__file__).parent))

# Import and run server
from stock_mcp import main

if __name__ == "__main__":
    main()
