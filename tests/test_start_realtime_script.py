import os
import subprocess
import sys
from pathlib import Path


def _script_path() -> Path:
    return Path(__file__).resolve().parents[1] / "scripts" / "start_realtime_system.sh"


def test_start_script_check_requires_secrets(tmp_path: Path) -> None:
    script = _script_path()
    env = {
        "PATH": os.environ.get("PATH", ""),
        "HOME": str(tmp_path),
        "PYBT_BASE_DIR": str(tmp_path / "base"),
        "PYBT_PYTHON": sys.executable,
    }
    proc = subprocess.run(
        ["bash", str(script), "--check"],
        env=env,
        capture_output=True,
        text=True,
    )

    assert proc.returncode != 0
    assert "Missing required env vars" in (proc.stderr + proc.stdout)


def test_start_script_check_passes_with_required_env(tmp_path: Path) -> None:
    script = _script_path()
    env = {
        "PATH": os.environ.get("PATH", ""),
        "HOME": str(tmp_path),
        "PYBT_BASE_DIR": str(tmp_path / "base"),
        "PYBT_PYTHON": sys.executable,
        "PYBT_API_KEY": "k",
        "TELEGRAM_BOT_TOKEN": "token",
        "TELEGRAM_ADMIN_PASSWORD": "pwd",
    }
    proc = subprocess.run(
        ["bash", str(script), "--check"],
        env=env,
        capture_output=True,
        text=True,
    )

    assert proc.returncode == 0
    assert "Environment check passed" in proc.stdout
