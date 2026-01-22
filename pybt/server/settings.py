from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ServerSettings:
    """Runtime settings for the local server.

    Keep this intentionally small; environment parsing happens in __main__.
    """

    base_dir: Path
    api_key: str
    max_concurrent_runs: int = 4

    @property
    def configs_dir(self) -> Path:
        return self.base_dir / "configs"

    @property
    def runs_dir(self) -> Path:
        return self.base_dir / "runs"
