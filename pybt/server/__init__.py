"""PyBT server layer (local-first).

This package provides a lightweight HTTP API to manage configs and run
concurrent backtests / realtime runs in isolated worker processes.
"""

from .app import create_app

__all__ = ["create_app"]
