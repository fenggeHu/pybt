from ..models import ValidationResult


def validate_config_payload(config: dict) -> ValidationResult:
    """Use the existing PyBT loader to validate a config payload."""
    try:
        from pybt import load_engine_from_dict

        load_engine_from_dict(config)
        return ValidationResult(ok=True, detail="valid")
    except Exception as exc:  # pragma: no cover - defensive
        return ValidationResult(ok=False, detail=str(exc))
