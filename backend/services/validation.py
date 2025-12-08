import json
import tempfile
from pathlib import Path

from ..models import ValidationResult


def validate_config_payload(config: dict) -> ValidationResult:
    """Use the existing PyBT loader to validate a config payload."""
    try:
        from pybt import load_engine_from_json

        with tempfile.TemporaryDirectory() as td:
            cfg_path = Path(td) / "config.json"
            cfg_path.write_text(json.dumps(config, ensure_ascii=False), encoding="utf-8")
            load_engine_from_json(cfg_path)
        return ValidationResult(ok=True, detail="valid")
    except Exception as exc:  # pragma: no cover - defensive
        return ValidationResult(ok=False, detail=str(exc))
