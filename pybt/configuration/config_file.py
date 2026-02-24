"""Helpers for loading JSON/JSONC config files with local $ref support."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Mapping


def loads_jsonc(text: str) -> Any:
    """Parse JSONC text (supports // and /* */ comments + trailing commas)."""

    return json.loads(_remove_trailing_commas(_strip_jsonc_comments(text)))


def load_config_file(path: str | Path) -> Any:
    """Load a config file and recursively resolve local $ref entries."""

    cfg_path = Path(path)
    raw = loads_jsonc(cfg_path.read_text(encoding="utf-8"))
    return resolve_config_refs(raw, base_dir=cfg_path.parent, source_path=cfg_path)


def load_config_dict(path: str | Path) -> dict[str, Any]:
    raw = load_config_file(path)
    if not isinstance(raw, Mapping):
        raise ValueError("Config JSON must be an object")
    return dict(raw)


def resolve_config_refs(
    value: Any,
    *,
    base_dir: Path | None = None,
    source_path: str | Path | None = None,
) -> Any:
    """Resolve $ref recursively on an in-memory config object."""

    chain: list[Path] = []
    if source_path is not None:
        chain.append(Path(source_path).resolve())
    return _resolve_refs(value, base_dir=base_dir, chain=chain)


def _resolve_refs(value: Any, *, base_dir: Path | None, chain: list[Path]) -> Any:
    if isinstance(value, list):
        return [_resolve_refs(item, base_dir=base_dir, chain=chain) for item in value]
    if not isinstance(value, Mapping):
        return value

    if "$ref" in value:
        ref = value.get("$ref")
        if not isinstance(ref, str) or not ref.strip():
            raise ValueError("Invalid $ref value")
        ref_path, ref_fragment = _parse_ref(ref, base_dir=base_dir)
        if ref_path in chain:
            raise ValueError(f"Cyclic $ref detected: {ref_path}")
        ref_raw = loads_jsonc(ref_path.read_text(encoding="utf-8"))
        if ref_fragment:
            ref_raw = _extract_ref_fragment(ref_raw, ref_fragment)
        resolved_ref = _resolve_refs(
            ref_raw, base_dir=ref_path.parent, chain=[*chain, ref_path]
        )
        if not isinstance(resolved_ref, Mapping):
            if len(value) == 1:
                return resolved_ref
            raise ValueError(f"$ref target must be an object when overriding: {ref}")
        overrides = {
            str(k): _resolve_refs(v, base_dir=base_dir, chain=chain)
            for k, v in value.items()
            if k != "$ref"
        }
        return _merge_dicts(dict(resolved_ref), overrides)

    return {
        str(k): _resolve_refs(v, base_dir=base_dir, chain=chain)
        for k, v in value.items()
    }


def _merge_dicts(base: dict[str, Any], override: Mapping[str, Any]) -> dict[str, Any]:
    out = dict(base)
    for key, value in override.items():
        if key in out and isinstance(out[key], Mapping) and isinstance(value, Mapping):
            out[key] = _merge_dicts(dict(out[key]), value)
        else:
            out[key] = value
    return out


def _parse_ref(ref: str, *, base_dir: Path | None) -> tuple[Path, str]:
    ref_body = ref.strip()
    path_part, _, fragment = ref_body.partition("#")
    if not path_part.strip():
        raise ValueError("Invalid $ref value")

    expanded = Path(os.path.expandvars(path_part.strip())).expanduser()
    if expanded.is_absolute():
        ref_path = expanded.resolve()
    else:
        anchor = (base_dir or Path.cwd()).resolve()
        ref_path = (anchor / expanded).resolve()
    return ref_path, fragment.strip()


def _extract_ref_fragment(value: Any, fragment: str) -> Any:
    if fragment.startswith("/"):
        return _extract_json_pointer(value, fragment)
    if not fragment:
        return value
    return _extract_dot_path(value, fragment)


def _extract_json_pointer(value: Any, pointer: str) -> Any:
    cur = value
    for token in pointer.split("/")[1:]:
        key = token.replace("~1", "/").replace("~0", "~")
        if isinstance(cur, Mapping):
            if key not in cur:
                raise ValueError(f"$ref fragment not found: #{pointer}")
            cur = cur[key]
            continue
        if isinstance(cur, list):
            try:
                idx = int(key)
            except ValueError as exc:
                raise ValueError(f"$ref fragment not found: #{pointer}") from exc
            if idx < 0 or idx >= len(cur):
                raise ValueError(f"$ref fragment not found: #{pointer}")
            cur = cur[idx]
            continue
        raise ValueError(f"$ref fragment not found: #{pointer}")
    return cur


def _extract_dot_path(value: Any, path: str) -> Any:
    cur = value
    for token in path.split("."):
        key = token.strip()
        if not key:
            raise ValueError(f"Invalid $ref fragment: #{path}")
        if isinstance(cur, Mapping):
            if key not in cur:
                raise ValueError(f"$ref fragment not found: #{path}")
            cur = cur[key]
            continue
        if isinstance(cur, list):
            try:
                idx = int(key)
            except ValueError as exc:
                raise ValueError(f"$ref fragment not found: #{path}") from exc
            if idx < 0 or idx >= len(cur):
                raise ValueError(f"$ref fragment not found: #{path}")
            cur = cur[idx]
            continue
        raise ValueError(f"$ref fragment not found: #{path}")
    return cur


def _strip_jsonc_comments(text: str) -> str:
    out: list[str] = []
    in_string = False
    escaped = False
    in_line_comment = False
    in_block_comment = False
    i = 0
    n = len(text)
    while i < n:
        ch = text[i]
        nxt = text[i + 1] if i + 1 < n else ""

        if in_line_comment:
            if ch == "\n":
                in_line_comment = False
                out.append(ch)
            i += 1
            continue

        if in_block_comment:
            if ch == "*" and nxt == "/":
                in_block_comment = False
                i += 2
                continue
            if ch == "\n":
                out.append(ch)
            i += 1
            continue

        if in_string:
            out.append(ch)
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == '"':
                in_string = False
            i += 1
            continue

        if ch == '"':
            in_string = True
            out.append(ch)
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

        out.append(ch)
        i += 1

    return "".join(out)


def _remove_trailing_commas(text: str) -> str:
    out: list[str] = []
    in_string = False
    escaped = False
    i = 0
    n = len(text)
    while i < n:
        ch = text[i]
        if in_string:
            out.append(ch)
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == '"':
                in_string = False
            i += 1
            continue

        if ch == '"':
            in_string = True
            out.append(ch)
            i += 1
            continue

        if ch == ",":
            j = i + 1
            while j < n and text[j] in " \t\r\n":
                j += 1
            if j < n and text[j] in "]}":
                i += 1
                continue

        out.append(ch)
        i += 1
    return "".join(out)
