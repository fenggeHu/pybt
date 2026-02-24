"""User-level sensitive configuration bootstrap helpers."""

from __future__ import annotations

from pathlib import Path


def default_user_config_path() -> Path:
    return Path.home() / ".pybt" / "config.jsonc"


def ensure_user_config(path: str | Path | None = None) -> Path:
    """Ensure ~/.pybt/config.jsonc exists and return its path."""

    cfg_path = Path(path) if path is not None else default_user_config_path()
    cfg_path = cfg_path.expanduser().resolve()
    cfg_path.parent.mkdir(parents=True, exist_ok=True)
    if not cfg_path.exists():
        cfg_path.write_text(_default_user_config_text(), encoding="utf-8")
    return cfg_path


def _default_user_config_text() -> str:
    return """{
  // User-local secrets (do not commit to git)
  // Usage example in project configs:
  // "headers": {"$ref": "~/.pybt/config.jsonc#secrets.sina.headers"}
  "secrets": {
    "eastmoney": {
      "token": "",
      "headers": {},
      "snapshot_headers": {}
    },
    "sina": {
      "headers": {}
    }
  }
}
"""


__all__ = ["default_user_config_path", "ensure_user_config"]
