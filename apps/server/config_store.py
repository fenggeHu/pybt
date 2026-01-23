from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping


_SAFE_NAME = re.compile(r"^[A-Za-z0-9_.-]+\.json$")


class ConfigNameError(ValueError):
    pass


@dataclass
class ConfigStore:
    configs_dir: Path

    def __post_init__(self) -> None:
        self.configs_dir.mkdir(parents=True, exist_ok=True)

    def _path_for(self, name: str) -> Path:
        if not _SAFE_NAME.match(name):
            raise ConfigNameError(
                "Invalid config name. Use letters/numbers/._- and end with .json"
            )
        return self.configs_dir / name

    def list(self) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        for path in sorted(self.configs_dir.glob("*.json")):
            st = path.stat()
            items.append(
                {
                    "name": path.name,
                    "size_bytes": st.st_size,
                    "mtime": st.st_mtime,
                }
            )
        return items

    def load(self, name: str) -> Mapping[str, Any]:
        path = self._path_for(name)
        raw = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            raise ValueError("Config JSON must be an object")
        return raw

    def save(self, name: str, config: Mapping[str, Any], *, force: bool) -> None:
        path = self._path_for(name)
        if path.exists() and not force:
            raise FileExistsError(name)
        path.write_text(json.dumps(config, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
