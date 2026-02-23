"""Plugin registry and loader for config-driven engine assembly."""

from __future__ import annotations

from dataclasses import dataclass, field
from difflib import get_close_matches
from importlib.util import module_from_spec, spec_from_file_location
import logging
from pathlib import Path
from typing import Any, Mapping, Optional

from pybt.core.interfaces import (
    DataFeed,
    ExecutionHandler,
    PerformanceReporter,
    Portfolio,
    RiskManager,
    Strategy,
)

from .config_file import load_config_dict

PLUGIN_KINDS = frozenset(
    {"data_feed", "strategy", "portfolio", "execution", "risk", "reporter"}
)


def find_default_registry_path(
    *, search_from: Optional[Path] = None, fallback: Optional[Path] = None
) -> Path:
    """Locate plugin.jsonc by walking parent directories.

    Search order:
    1) `search_from` and its parents
    2) current working directory and its parents
    3) module root (`pybt/configuration/..`) and its parents
    4) fallback path or `plugins/plugin.jsonc`
    """

    roots: list[Path] = []
    if search_from is not None:
        roots.append(search_from.resolve())
    roots.append(Path.cwd().resolve())
    roots.append(Path(__file__).resolve().parent)

    visited: set[Path] = set()
    for root in roots:
        for candidate_base in (root, *root.parents):
            if candidate_base in visited:
                continue
            visited.add(candidate_base)
            candidate = candidate_base / "plugins" / "plugin.jsonc"
            if candidate.exists():
                return candidate.resolve()

    if fallback is not None:
        return fallback.resolve()
    return Path("plugins/plugin.jsonc").resolve()


class PluginConfigError(ValueError):
    """Error with structured plugin loading metadata."""

    def __init__(
        self,
        code: str,
        message: str,
        *,
        plugin_name: Optional[str] = None,
        kind: Optional[str] = None,
        slot: Optional[str] = None,
    ) -> None:
        self.code = code
        self.plugin_name = plugin_name
        self.kind = kind
        self.slot = slot
        super().__init__(self._format_message(message))

    def _format_message(self, message: str) -> str:
        bits = [self.code, message]
        if self.plugin_name:
            bits.append(f"plugin={self.plugin_name}")
        if self.kind:
            bits.append(f"kind={self.kind}")
        if self.slot:
            bits.append(f"slot={self.slot}")
        return " | ".join(bits)


@dataclass(frozen=True)
class PluginParamSpec:
    name: str
    type: str
    required: bool = False
    default: Optional[Any] = None
    description: Optional[str] = None


@dataclass(frozen=True)
class PluginSpec:
    name: str
    kind: str
    module: str
    entry: str
    enabled: bool
    defaults: dict[str, Any] = field(default_factory=dict)
    capabilities: dict[str, Any] = field(default_factory=dict)
    summary: str = ""
    params: list[PluginParamSpec] = field(default_factory=list)
    strict_params: bool = False


def _to_bool(value: Any, *, default: bool = True) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        return value.strip().lower() not in {"0", "false", "off", "no"}
    return bool(value)


def _clone(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(k): _clone(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_clone(v) for v in value]
    return value


def _coerce_param_value(
    value: Any,
    *,
    type_name: str,
    param_name: str,
    plugin_name: str,
    kind: str,
    slot: str,
) -> Any:
    raw = type_name.strip().lower()
    base = raw.split("[", 1)[0].strip()
    if base in {"", "any", "json"}:
        return value

    if base in {"str", "string"}:
        if not isinstance(value, str):
            raise PluginConfigError(
                "PLUGIN_INVALID_PARAMS",
                f"Param '{param_name}' must be a string",
                plugin_name=plugin_name,
                kind=kind,
                slot=slot,
            )
        return value

    if base in {"int", "integer"}:
        if isinstance(value, bool):
            raise PluginConfigError(
                "PLUGIN_INVALID_PARAMS",
                f"Param '{param_name}' must be an int",
                plugin_name=plugin_name,
                kind=kind,
                slot=slot,
            )
        if isinstance(value, int):
            return value
        if isinstance(value, float) and float(value).is_integer():
            return int(value)
        if isinstance(value, str):
            try:
                return int(value.strip())
            except Exception as exc:
                raise PluginConfigError(
                    "PLUGIN_INVALID_PARAMS",
                    f"Param '{param_name}' must be an int",
                    plugin_name=plugin_name,
                    kind=kind,
                    slot=slot,
                ) from exc
        raise PluginConfigError(
            "PLUGIN_INVALID_PARAMS",
            f"Param '{param_name}' must be an int",
            plugin_name=plugin_name,
            kind=kind,
            slot=slot,
        )

    if base in {"float", "number"}:
        if isinstance(value, bool):
            raise PluginConfigError(
                "PLUGIN_INVALID_PARAMS",
                f"Param '{param_name}' must be a float",
                plugin_name=plugin_name,
                kind=kind,
                slot=slot,
            )
        if isinstance(value, (int, float)):
            return float(value)
        if isinstance(value, str):
            try:
                return float(value.strip())
            except Exception as exc:
                raise PluginConfigError(
                    "PLUGIN_INVALID_PARAMS",
                    f"Param '{param_name}' must be a float",
                    plugin_name=plugin_name,
                    kind=kind,
                    slot=slot,
                ) from exc
        raise PluginConfigError(
            "PLUGIN_INVALID_PARAMS",
            f"Param '{param_name}' must be a float",
            plugin_name=plugin_name,
            kind=kind,
            slot=slot,
        )

    if base in {"bool", "boolean"}:
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            token = value.strip().lower()
            if token in {"1", "true", "on", "yes"}:
                return True
            if token in {"0", "false", "off", "no"}:
                return False
        if isinstance(value, (int, float)):
            return bool(value)
        raise PluginConfigError(
            "PLUGIN_INVALID_PARAMS",
            f"Param '{param_name}' must be a bool",
            plugin_name=plugin_name,
            kind=kind,
            slot=slot,
        )

    if base in {"object", "dict", "map", "mapping"}:
        if not isinstance(value, Mapping):
            raise PluginConfigError(
                "PLUGIN_INVALID_PARAMS",
                f"Param '{param_name}' must be an object",
                plugin_name=plugin_name,
                kind=kind,
                slot=slot,
            )
        return {str(k): _clone(v) for k, v in value.items()}

    if base == "list":
        if not isinstance(value, list):
            raise PluginConfigError(
                "PLUGIN_INVALID_PARAMS",
                f"Param '{param_name}' must be an array",
                plugin_name=plugin_name,
                kind=kind,
                slot=slot,
            )
        return [_clone(v) for v in value]

    # For custom type tags (e.g. list[bar], enum aliases), use base behavior.
    if raw.startswith("list["):
        if not isinstance(value, list):
            raise PluginConfigError(
                "PLUGIN_INVALID_PARAMS",
                f"Param '{param_name}' must be an array",
                plugin_name=plugin_name,
                kind=kind,
                slot=slot,
            )
        return [_clone(v) for v in value]
    return value


def _unknown_param_hint(name: str, *, declared: set[str]) -> str:
    matches = get_close_matches(name, sorted(declared), n=1, cutoff=0.72)
    if not matches:
        return name
    return f"{name} (did you mean '{matches[0]}'?)"


def deep_merge(base: Mapping[str, Any], override: Mapping[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {str(k): _clone(v) for k, v in base.items()}
    for key, value in override.items():
        skey = str(key)
        current = out.get(skey)
        if isinstance(current, Mapping) and isinstance(value, Mapping):
            out[skey] = deep_merge(dict(current), value)
        else:
            out[skey] = _clone(value)
    return out


class PluginRegistry:
    """In-memory representation of plugin.jsonc."""

    def __init__(self, *, source_path: Path, plugin_dir: Path, specs: list[PluginSpec]):
        self.source_path = source_path
        self.plugin_dir = plugin_dir
        self._spec_by_name = {spec.name: spec for spec in specs}

    @classmethod
    def from_file(cls, path: str | Path) -> "PluginRegistry":
        source_path = Path(path).resolve()
        payload = load_config_dict(source_path)
        strict_params_default = _to_bool(payload.get("strict_params_default"), default=False)

        plugin_dir_raw = payload.get("plugin_dir", "./plugins")
        if not isinstance(plugin_dir_raw, str) or not plugin_dir_raw.strip():
            raise PluginConfigError(
                "PLUGIN_INVALID_REGISTRY",
                "plugin_dir must be a non-empty string",
            )

        plugin_dir = Path(plugin_dir_raw)
        if not plugin_dir.is_absolute():
            plugin_dir = (source_path.parent / plugin_dir).resolve()

        raw_plugins = payload.get("plugins")
        if not isinstance(raw_plugins, list):
            raise PluginConfigError(
                "PLUGIN_INVALID_REGISTRY", "plugins must be an array"
            )

        seen: set[str] = set()
        specs: list[PluginSpec] = []
        for idx, item in enumerate(raw_plugins):
            if not isinstance(item, Mapping):
                raise PluginConfigError(
                    "PLUGIN_INVALID_REGISTRY", f"plugins[{idx}] must be an object"
                )
            name = item.get("name")
            if not isinstance(name, str) or not name.strip():
                raise PluginConfigError(
                    "PLUGIN_INVALID_REGISTRY", f"plugins[{idx}].name is required"
                )
            name = name.strip()
            if name in seen:
                raise PluginConfigError(
                    "PLUGIN_INVALID_REGISTRY", f"Duplicate plugin name: {name}"
                )
            seen.add(name)

            kind = item.get("kind")
            if not isinstance(kind, str) or kind not in PLUGIN_KINDS:
                raise PluginConfigError(
                    "PLUGIN_INVALID_KIND",
                    f"plugins[{idx}].kind must be one of {sorted(PLUGIN_KINDS)}",
                    plugin_name=name,
                )

            module = item.get("module")
            if module is None:
                module = name
            if not isinstance(module, str) or not module.strip():
                raise PluginConfigError(
                    "PLUGIN_INVALID_REGISTRY",
                    f"plugins[{idx}].module must be a non-empty string",
                    plugin_name=name,
                    kind=kind,
                )

            entry = item.get("entry", "create")
            if not isinstance(entry, str) or not entry.strip():
                raise PluginConfigError(
                    "PLUGIN_INVALID_REGISTRY",
                    f"plugins[{idx}].entry must be a non-empty string",
                    plugin_name=name,
                    kind=kind,
                )

            defaults_raw = item.get("defaults", {})
            if not isinstance(defaults_raw, Mapping):
                raise PluginConfigError(
                    "PLUGIN_INVALID_REGISTRY",
                    f"plugins[{idx}].defaults must be an object",
                    plugin_name=name,
                    kind=kind,
                )

            capabilities_raw = item.get("capabilities", {})
            if not isinstance(capabilities_raw, Mapping):
                raise PluginConfigError(
                    "PLUGIN_INVALID_REGISTRY",
                    f"plugins[{idx}].capabilities must be an object",
                    plugin_name=name,
                    kind=kind,
                )

            summary_raw = item.get("summary", "")
            summary = str(summary_raw) if summary_raw is not None else ""

            params: list[PluginParamSpec] = []
            params_raw = item.get("params")
            if params_raw is not None:
                if not isinstance(params_raw, list):
                    raise PluginConfigError(
                        "PLUGIN_INVALID_REGISTRY",
                        f"plugins[{idx}].params must be an array",
                        plugin_name=name,
                        kind=kind,
                    )
                for pidx, one in enumerate(params_raw):
                    if not isinstance(one, Mapping):
                        raise PluginConfigError(
                            "PLUGIN_INVALID_REGISTRY",
                            f"plugins[{idx}].params[{pidx}] must be an object",
                            plugin_name=name,
                            kind=kind,
                        )
                    pname = one.get("name")
                    ptype = one.get("type")
                    if not isinstance(pname, str) or not pname.strip():
                        raise PluginConfigError(
                            "PLUGIN_INVALID_REGISTRY",
                            f"plugins[{idx}].params[{pidx}].name is required",
                            plugin_name=name,
                            kind=kind,
                        )
                    if not isinstance(ptype, str) or not ptype.strip():
                        raise PluginConfigError(
                            "PLUGIN_INVALID_REGISTRY",
                            f"plugins[{idx}].params[{pidx}].type is required",
                            plugin_name=name,
                            kind=kind,
                        )
                    params.append(
                        PluginParamSpec(
                            name=pname.strip(),
                            type=ptype.strip(),
                            required=_to_bool(one.get("required"), default=False),
                            default=_clone(one.get("default")),
                            description=(
                                str(one.get("description"))
                                if one.get("description") is not None
                                else None
                            ),
                        )
                    )

            specs.append(
                PluginSpec(
                    name=name,
                    kind=kind,
                    module=module.strip(),
                    entry=entry.strip(),
                    enabled=_to_bool(item.get("enabled"), default=True),
                    defaults={str(k): _clone(v) for k, v in defaults_raw.items()},
                    capabilities={
                        str(k): _clone(v) for k, v in capabilities_raw.items()
                    },
                    summary=summary,
                    params=params,
                    strict_params=_to_bool(
                        item.get("strict_params"), default=strict_params_default
                    ),
                )
            )

        return cls(source_path=source_path, plugin_dir=plugin_dir, specs=specs)

    def get(self, name: str) -> Optional[PluginSpec]:
        return self._spec_by_name.get(name)

    def list_specs(self) -> list[PluginSpec]:
        return list(self._spec_by_name.values())


EXPECTED_INTERFACE: dict[str, type[Any]] = {
    "data_feed": DataFeed,
    "strategy": Strategy,
    "portfolio": Portfolio,
    "execution": ExecutionHandler,
    "risk": RiskManager,
    "reporter": PerformanceReporter,
}


class PluginLoader:
    """Loads plugin modules and instantiates components from runtime config."""

    def __init__(self, registry: PluginRegistry):
        self.registry = registry
        self._module_cache: dict[Path, Any] = {}

    def create_component(
        self,
        *,
        slot: str,
        kind: str,
        component: Mapping[str, Any],
        run_id: str,
        engine_config: Mapping[str, Any],
    ) -> Any:
        plugin_name_raw = component.get("plugin")
        if not isinstance(plugin_name_raw, str) or not plugin_name_raw.strip():
            raise PluginConfigError(
                "PLUGIN_INVALID_PARAMS",
                f"{slot}.plugin is required",
                kind=kind,
                slot=slot,
            )
        plugin_name = plugin_name_raw.strip()
        spec = self.registry.get(plugin_name)
        if spec is None:
            raise PluginConfigError(
                "PLUGIN_NOT_FOUND",
                "Plugin not found in plugin registry",
                plugin_name=plugin_name,
                kind=kind,
                slot=slot,
            )
        if not spec.enabled:
            raise PluginConfigError(
                "PLUGIN_DISABLED",
                "Plugin is disabled",
                plugin_name=plugin_name,
                kind=kind,
                slot=slot,
            )
        if spec.kind != kind:
            raise PluginConfigError(
                "PLUGIN_KIND_MISMATCH",
                f"Expected kind {kind} but got {spec.kind}",
                plugin_name=plugin_name,
                kind=kind,
                slot=slot,
            )

        params_raw = component.get("params", {})
        if not isinstance(params_raw, Mapping):
            raise PluginConfigError(
                "PLUGIN_INVALID_PARAMS",
                f"{slot}.params must be an object",
                plugin_name=plugin_name,
                kind=kind,
                slot=slot,
            )
        params = self._apply_param_specs(
            spec,
            deep_merge(spec.defaults, params_raw),
            slot=slot,
        )
        self._validate_capabilities(spec, params, slot=slot)

        module = self._load_module(spec)
        entry_fn = getattr(module, spec.entry, None)
        if not callable(entry_fn):
            raise PluginConfigError(
                "PLUGIN_ENTRY_NOT_FOUND",
                f"Entry {spec.entry} is not callable",
                plugin_name=plugin_name,
                kind=kind,
                slot=slot,
            )

        ctx = {
            "plugin_name": plugin_name,
            "kind": kind,
            "slot": slot,
            "run_id": run_id,
            "logger": logging.getLogger(f"pybt.plugin.{plugin_name}"),
            "engine_config": dict(engine_config),
        }

        try:
            instance = entry_fn(params, ctx)
        except PluginConfigError:
            raise
        except Exception as exc:
            raise PluginConfigError(
                "PLUGIN_CREATE_FAILED",
                str(exc),
                plugin_name=plugin_name,
                kind=kind,
                slot=slot,
            ) from exc

        expected = EXPECTED_INTERFACE[kind]
        if not isinstance(instance, expected):
            raise PluginConfigError(
                "PLUGIN_INTERFACE_MISMATCH",
                f"Plugin must return {expected.__name__}",
                plugin_name=plugin_name,
                kind=kind,
                slot=slot,
            )
        return instance

    def _validate_capabilities(
        self, spec: PluginSpec, params: Mapping[str, Any], *, slot: str
    ) -> None:
        transports = spec.capabilities.get("transports")
        if transports is None:
            return
        if not isinstance(transports, list):
            raise PluginConfigError(
                "PLUGIN_INVALID_REGISTRY",
                "capabilities.transports must be an array",
                plugin_name=spec.name,
                kind=spec.kind,
                slot=slot,
            )
        normalized = {str(one).strip().lower() for one in transports if str(one).strip()}
        transport_value = params.get("transport")
        if transport_value is None:
            return
        transport = str(transport_value).strip().lower()
        if transport and transport not in normalized:
            raise PluginConfigError(
                "PLUGIN_UNSUPPORTED_TRANSPORT",
                f"Unsupported transport: {transport}",
                plugin_name=spec.name,
                kind=spec.kind,
                slot=slot,
            )

    def _apply_param_specs(
        self, spec: PluginSpec, params: dict[str, Any], *, slot: str
    ) -> dict[str, Any]:
        out = dict(params)
        declared = {one.name for one in spec.params}
        declared.update(str(k) for k in spec.defaults.keys())
        if spec.strict_params:
            unknown = sorted(k for k in out.keys() if k not in declared)
            if unknown:
                rendered = [
                    _unknown_param_hint(name, declared=declared) for name in unknown
                ]
                raise PluginConfigError(
                    "PLUGIN_INVALID_PARAMS",
                    f"Unknown params: {', '.join(rendered)}",
                    plugin_name=spec.name,
                    kind=spec.kind,
                    slot=slot,
                )
        for one in spec.params:
            if one.name not in out and one.default is not None:
                out[one.name] = _clone(one.default)
            if one.required and (one.name not in out or out.get(one.name) is None):
                raise PluginConfigError(
                    "PLUGIN_INVALID_PARAMS",
                    f"Missing required param: {one.name}",
                    plugin_name=spec.name,
                    kind=spec.kind,
                    slot=slot,
                )
            if one.name in out and out.get(one.name) is not None:
                out[one.name] = _coerce_param_value(
                    out[one.name],
                    type_name=one.type,
                    param_name=one.name,
                    plugin_name=spec.name,
                    kind=spec.kind,
                    slot=slot,
                )
            if (
                one.required
                and one.type.strip().lower() in {"str", "string"}
                and isinstance(out.get(one.name), str)
                and not out[one.name].strip()
            ):
                raise PluginConfigError(
                    "PLUGIN_INVALID_PARAMS",
                    f"Missing required param: {one.name}",
                    plugin_name=spec.name,
                    kind=spec.kind,
                    slot=slot,
                )
        return out

    def _load_module(self, spec: PluginSpec) -> Any:
        path = self._resolve_module_path(spec)
        module = self._module_cache.get(path)
        if module is not None:
            return module

        module_name = f"pybt_dynamic_plugin_{spec.name}_{abs(hash(path))}"
        mod_spec = spec_from_file_location(module_name, path)
        if mod_spec is None or mod_spec.loader is None:
            raise PluginConfigError(
                "PLUGIN_ENTRY_NOT_FOUND",
                f"Unable to load plugin module from {path}",
                plugin_name=spec.name,
                kind=spec.kind,
            )
        module = module_from_spec(mod_spec)
        mod_spec.loader.exec_module(module)
        self._module_cache[path] = module
        return module

    def _resolve_module_path(self, spec: PluginSpec) -> Path:
        module_value = spec.module
        module_path = Path(module_value)
        if module_path.suffix != ".py":
            module_path = module_path.with_suffix(".py")

        if module_path.is_absolute():
            resolved = module_path.resolve()
        else:
            resolved = (self.registry.plugin_dir / module_path).resolve()

        root = self.registry.plugin_dir.resolve()
        if not _is_subpath(resolved, root):
            raise PluginConfigError(
                "PLUGIN_ENTRY_NOT_FOUND",
                "Plugin module path must be inside plugin_dir",
                plugin_name=spec.name,
                kind=spec.kind,
            )
        if not resolved.exists() or not resolved.is_file():
            raise PluginConfigError(
                "PLUGIN_ENTRY_NOT_FOUND",
                f"Plugin module not found: {resolved}",
                plugin_name=spec.name,
                kind=spec.kind,
            )
        return resolved


def _is_subpath(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


__all__ = [
    "PLUGIN_KINDS",
    "PluginConfigError",
    "PluginLoader",
    "PluginParamSpec",
    "PluginRegistry",
    "PluginSpec",
    "deep_merge",
    "find_default_registry_path",
]
