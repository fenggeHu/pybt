#!/usr/bin/env python3
"""
Installation script for stock-mcp server.
"""

import subprocess
import sys


def install_dependencies():
    """Install required dependencies."""
    print("Installing stock-mcp dependencies...")

    dependencies = [
        "mcp>=1.0.0",
        "akshare>=1.18.0",
        "pandas>=2.0.0",
        "numpy>=1.24.0",
        "httpx>=0.27.0",
        "pydantic>=2.0.0",
    ]

    for dep in dependencies:
        print(f"Installing {dep}...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", dep])

    print("\n✅ All dependencies installed successfully!")
    print("\nYou can now run the server with:")
    print("  python -m stock_mcp")


if __name__ == "__main__":
    try:
        install_dependencies()
    except subprocess.CalledProcessError as e:
        print(f"\n❌ Installation failed: {e}")
        sys.exit(1)
