from __future__ import annotations

import os
from pathlib import Path

import uvicorn

from apps.server.app import create_app
from apps.server.settings import ServerSettings


def main() -> None:
    host = os.environ.get("PYBT_SERVER_HOST", "127.0.0.1")
    port = int(os.environ.get("PYBT_SERVER_PORT", "8765"))
    api_key = os.environ.get("PYBT_API_KEY", "123")
    if not api_key:
        raise SystemExit("PYBT_API_KEY is required")
    base_dir = Path(os.environ.get("PYBT_BASE_DIR", str(Path.home() / ".pybt")))
    max_runs = int(os.environ.get("PYBT_MAX_CONCURRENT_RUNS", "4"))

    settings = ServerSettings(base_dir=base_dir, api_key=api_key, max_concurrent_runs=max_runs)
    app = create_app(settings)
    uvicorn.run(app, host=host, port=port, log_level="info")


if __name__ == "__main__":
    main()
