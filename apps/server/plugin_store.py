from __future__ import annotations
from pathlib import Path
import threading
from typing import Any, Mapping, Optional

from pybt.configuration.config_file import load_config_dict, loads_jsonc
from pybt.configuration.plugins import PluginRegistry, find_default_registry_path


class PluginStoreError(ValueError):
    pass


_LOCKS_GUARD = threading.Lock()
_PATH_LOCKS: dict[Path, threading.Lock] = {}


def _path_lock(path: Path) -> threading.Lock:
    resolved = path.resolve()
    with _LOCKS_GUARD:
        lock = _PATH_LOCKS.get(resolved)
        if lock is None:
            lock = threading.Lock()
            _PATH_LOCKS[resolved] = lock
        return lock


class PluginStore:
    def __init__(self, registry_path: Optional[Path] = None) -> None:
        self.registry_path = (
            registry_path.resolve()
            if registry_path is not None
            else find_default_registry_path()
        )

    def list(
        self,
        *,
        kind: Optional[str] = None,
        enabled: Optional[bool] = None,
    ) -> list[dict[str, Any]]:
        payload = load_config_dict(self.registry_path)
        plugins = payload.get("plugins")
        if not isinstance(plugins, list):
            raise PluginStoreError("plugins must be an array")
        out: list[dict[str, Any]] = []
        for item in plugins:
            if not isinstance(item, Mapping):
                continue
            name = str(item.get("name", "")).strip()
            if not name:
                continue
            one_kind = str(item.get("kind", "")).strip()
            one_enabled = self._to_bool(item.get("enabled"), default=True)
            if kind is not None and one_kind != kind:
                continue
            if enabled is not None and one_enabled != enabled:
                continue
            out.append(
                {
                    "name": name,
                    "kind": one_kind,
                    "enabled": one_enabled,
                    "summary": str(item.get("summary", "")).strip(),
                    "module": str(item.get("module", name)).strip() or name,
                    "entry": str(item.get("entry", "create")).strip() or "create",
                }
            )
        out.sort(key=lambda x: (str(x.get("kind", "")), str(x.get("name", ""))))
        return out

    def set_enabled(self, plugin_name: str, *, enabled: bool) -> dict[str, Any]:
        name = plugin_name.strip()
        if not name:
            raise PluginStoreError("plugin name is required")

        lock = _path_lock(self.registry_path)
        with lock:
            before_text = self.registry_path.read_text(encoding="utf-8")
            try:
                after_text, meta = _toggle_plugin_enabled_in_registry_text(
                    before_text, plugin_name=name, enabled=bool(enabled)
                )
            except KeyError:
                raise
            except Exception as exc:
                raise PluginStoreError(str(exc)) from exc

            tmp_path = self.registry_path.with_suffix(self.registry_path.suffix + ".tmp")
            try:
                tmp_path.write_text(after_text, encoding="utf-8")
                tmp_path.replace(self.registry_path)
                # Validate registry after mutation.
                PluginRegistry.from_file(self.registry_path)
            except Exception:
                self.registry_path.write_text(before_text, encoding="utf-8")
                raise
            finally:
                if tmp_path.exists():
                    tmp_path.unlink(missing_ok=True)

            return {
                "name": meta["name"],
                "kind": meta["kind"],
                "enabled": bool(enabled),
                "summary": meta["summary"],
            }

    @staticmethod
    def _to_bool(value: Any, *, default: bool) -> bool:
        if value is None:
            return default
        if isinstance(value, bool):
            return value
        if isinstance(value, (int, float)):
            return bool(value)
        if isinstance(value, str):
            return value.strip().lower() not in {"0", "false", "off", "no"}
        return bool(value)


def _toggle_plugin_enabled_in_registry_text(
    text: str, *, plugin_name: str, enabled: bool
) -> tuple[str, dict[str, str]]:
    start, end = _find_plugins_array_span(text)
    spans = _find_top_level_object_spans(text, start, end)
    for s, e in spans:
        raw_object = text[s:e]
        try:
            payload = loads_jsonc(raw_object)
        except Exception:
            continue
        if not isinstance(payload, Mapping):
            continue
        name = str(payload.get("name", "")).strip()
        if name != plugin_name:
            continue
        kind = str(payload.get("kind", "")).strip()
        summary = str(payload.get("summary", "")).strip()
        updated_object = _set_enabled_on_plugin_object(raw_object, enabled=enabled)
        return (
            text[:s] + updated_object + text[e:],
            {"name": name, "kind": kind, "summary": summary},
        )
    raise KeyError(plugin_name)


def _find_plugins_array_span(text: str) -> tuple[int, int]:
    key_idx = text.find('"plugins"')
    if key_idx < 0:
        raise PluginStoreError("plugins key not found in registry")
    colon_idx = text.find(":", key_idx)
    if colon_idx < 0:
        raise PluginStoreError("plugins key is invalid")
    arr_start = text.find("[", colon_idx)
    if arr_start < 0:
        raise PluginStoreError("plugins must be an array")
    arr_end = _find_matching_bracket(text, arr_start, "[", "]")
    return arr_start + 1, arr_end


def _find_matching_bracket(text: str, start: int, left: str, right: str) -> int:
    in_str = False
    escaped = False
    in_line_comment = False
    in_block_comment = False
    depth = 0
    i = start
    while i < len(text):
        ch = text[i]
        nxt = text[i + 1] if i + 1 < len(text) else ""
        if in_line_comment:
            if ch == "\n":
                in_line_comment = False
            i += 1
            continue
        if in_block_comment:
            if ch == "*" and nxt == "/":
                in_block_comment = False
                i += 2
                continue
            i += 1
            continue
        if in_str:
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == '"':
                in_str = False
            i += 1
            continue
        if ch == '"':
            in_str = True
            i += 1
            continue
        if ch == "/" and nxt == "/":
            in_line_comment = True
            i += 2
            continue
        if ch == "/" and nxt == "*":
            in_block_comment = True
            i += 2
            continue
        if ch == left:
            depth += 1
        elif ch == right:
            depth -= 1
            if depth == 0:
                return i
        i += 1
    raise PluginStoreError("unbalanced registry structure")


def _find_top_level_object_spans(
    text: str, start: int, end: int
) -> list[tuple[int, int]]:
    spans: list[tuple[int, int]] = []
    i = start
    in_str = False
    escaped = False
    in_line_comment = False
    in_block_comment = False
    while i < end:
        ch = text[i]
        nxt = text[i + 1] if i + 1 < end else ""
        if in_line_comment:
            if ch == "\n":
                in_line_comment = False
            i += 1
            continue
        if in_block_comment:
            if ch == "*" and nxt == "/":
                in_block_comment = False
                i += 2
                continue
            i += 1
            continue
        if in_str:
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == '"':
                in_str = False
            i += 1
            continue
        if ch == '"':
            in_str = True
            i += 1
            continue
        if ch == "/" and nxt == "/":
            in_line_comment = True
            i += 2
            continue
        if ch == "/" and nxt == "*":
            in_block_comment = True
            i += 2
            continue
        if ch == "{":
            obj_end = _find_matching_bracket(text, i, "{", "}")
            spans.append((i, obj_end + 1))
            i = obj_end + 1
            continue
        i += 1
    return spans


def _set_enabled_on_plugin_object(obj: str, *, enabled: bool) -> str:
    value = "true" if enabled else "false"
    span = _find_top_level_property_value_span(obj, "enabled")
    if span is not None:
        start, end = span
        return obj[:start] + value + obj[end:]

    close_idx = obj.rfind("}")
    if close_idx < 0:
        raise PluginStoreError("invalid plugin object")
    base_line_start = obj.rfind("\n", 0, close_idx)
    if base_line_start < 0:
        base_indent = ""
    else:
        base_indent = obj[base_line_start + 1 : close_idx]
    prop_indent = base_indent + "  "
    before = obj[:close_idx].rstrip()
    suffix = obj[close_idx:]
    if before.endswith("{"):
        insertion = f"\n{prop_indent}\"enabled\": {value}\n{base_indent}"
    else:
        insertion = f",\n{prop_indent}\"enabled\": {value}\n{base_indent}"
    return before + insertion + suffix


def _find_top_level_property_value_span(
    obj: str, key_name: str
) -> Optional[tuple[int, int]]:
    depth = 0
    i = 0
    in_str = False
    escaped = False
    in_line_comment = False
    in_block_comment = False
    while i < len(obj):
        ch = obj[i]
        nxt = obj[i + 1] if i + 1 < len(obj) else ""
        if in_line_comment:
            if ch == "\n":
                in_line_comment = False
            i += 1
            continue
        if in_block_comment:
            if ch == "*" and nxt == "/":
                in_block_comment = False
                i += 2
                continue
            i += 1
            continue
        if in_str:
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == '"':
                in_str = False
            i += 1
            continue
        if ch == '"':
            if depth == 1:
                key_end = _find_string_end(obj, i + 1)
                raw_key = obj[i + 1 : key_end]
                key = bytes(raw_key, "utf-8").decode("unicode_escape")
                j = key_end + 1
                while j < len(obj) and obj[j] in " \t\r\n":
                    j += 1
                if j < len(obj) and obj[j] == ":" and key == key_name:
                    value_start = j + 1
                    while value_start < len(obj) and obj[value_start] in " \t\r\n":
                        value_start += 1
                    value_end = _find_value_end(obj, value_start)
                    return value_start, value_end
                i = key_end + 1
                continue
            in_str = True
            i += 1
            continue
        if ch == "/" and nxt == "/":
            in_line_comment = True
            i += 2
            continue
        if ch == "/" and nxt == "*":
            in_block_comment = True
            i += 2
            continue
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
        i += 1
    return None


def _find_string_end(text: str, start: int) -> int:
    i = start
    escaped = False
    while i < len(text):
        ch = text[i]
        if escaped:
            escaped = False
        elif ch == "\\":
            escaped = True
        elif ch == '"':
            return i
        i += 1
    raise PluginStoreError("invalid string in plugin object")


def _find_value_end(text: str, start: int) -> int:
    i = start
    depth_obj = 0
    depth_arr = 0
    in_str = False
    escaped = False
    in_line_comment = False
    in_block_comment = False
    while i < len(text):
        ch = text[i]
        nxt = text[i + 1] if i + 1 < len(text) else ""
        if in_line_comment:
            if ch == "\n":
                in_line_comment = False
            i += 1
            continue
        if in_block_comment:
            if ch == "*" and nxt == "/":
                in_block_comment = False
                i += 2
                continue
            i += 1
            continue
        if in_str:
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == '"':
                in_str = False
            i += 1
            continue
        if ch == '"':
            in_str = True
            i += 1
            continue
        if ch == "/" and nxt == "/":
            in_line_comment = True
            i += 2
            continue
        if ch == "/" and nxt == "*":
            in_block_comment = True
            i += 2
            continue
        if ch == "{":
            depth_obj += 1
            i += 1
            continue
        if ch == "}":
            if depth_obj == 0 and depth_arr == 0:
                return i
            depth_obj -= 1
            i += 1
            continue
        if ch == "[":
            depth_arr += 1
            i += 1
            continue
        if ch == "]":
            depth_arr -= 1
            i += 1
            continue
        if ch == "," and depth_obj == 0 and depth_arr == 0:
            return i
        i += 1
    return len(text)
