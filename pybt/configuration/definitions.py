"""Definitions generated from plugin registry metadata."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Optional

from .plugins import PluginRegistry, find_default_registry_path


@dataclass(frozen=True)
class ParamDef:
    name: str
    type: str
    required: bool = False
    default: Optional[Any] = None
    description: Optional[str] = None


@dataclass(frozen=True)
class ComponentDef:
    category: str
    type: str
    summary: str
    params: list[ParamDef] = field(default_factory=list)


def _default_registry_path() -> Path:
    return find_default_registry_path()


_DEFINITION_CACHE: dict[Path, tuple[int, list[ComponentDef]]] = {}


def list_definitions(registry_path: Optional[str | Path] = None) -> list[ComponentDef]:
    """Return plugin definitions for form/documentation generation."""

    resolved = Path(registry_path or _default_registry_path()).resolve()
    mtime_ns = resolved.stat().st_mtime_ns
    cached = _DEFINITION_CACHE.get(resolved)
    if cached is not None and cached[0] == mtime_ns:
        return list(cached[1])

    registry = PluginRegistry.from_file(resolved)
    defs: list[ComponentDef] = []
    for spec in registry.list_specs():
        defs.append(
            ComponentDef(
                category=spec.kind,
                type=spec.name,
                summary=spec.summary or spec.name,
                params=[
                    ParamDef(
                        name=one.name,
                        type=one.type,
                        required=one.required,
                        default=one.default,
                        description=one.description,
                    )
                    for one in spec.params
                ],
            )
        )
    defs.sort(key=lambda item: (item.category, item.type))
    _DEFINITION_CACHE[resolved] = (mtime_ns, defs)
    return defs


def iter_definition_dicts() -> Iterable[dict[str, Any]]:
    """Yield definitions as plain dicts for API consumers."""

    for definition in list_definitions():
        yield {
            "category": definition.category,
            "type": definition.type,
            "summary": definition.summary,
            "params": [
                {
                    "name": param.name,
                    "type": param.type,
                    "required": param.required,
                    "default": param.default,
                    "description": param.description,
                }
                for param in definition.params
            ],
        }


__all__ = ["ComponentDef", "ParamDef", "iter_definition_dicts", "list_definitions"]
