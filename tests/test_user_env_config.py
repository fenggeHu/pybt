from pathlib import Path

from pybt.configuration.user_env import ensure_user_config


def test_ensure_user_config_creates_default_file(tmp_path: Path) -> None:
    target = tmp_path / ".pybt" / "config.jsonc"
    out = ensure_user_config(target)
    assert out == target.resolve()
    assert out.exists()
    text = out.read_text(encoding="utf-8")
    assert '"secrets"' in text
