"""Helpers for loading JSON/JSONC config files with local $ref support."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping


def loads_jsonc(text: str) -> Any:
    """Parse JSONC text (supports // and /* */ comments + trailing commas)."""

    return json.loads(_remove_trailing_commas(_strip_jsonc_comments(text)))


def load_config_file(path: str | Path) -> Any:
    """Load a config file and recursively resolve local $ref entries."""

    cfg_path = Path(path)
    raw = loads_jsonc(cfg_path.read_text(encoding="utf-8"))
    return _resolve_refs(raw, base_dir=cfg_path.parent, chain=[cfg_path.resolve()])


def load_config_dict(path: str | Path) -> dict[str, Any]:
    raw = load_config_file(path)
    if not isinstance(raw, Mapping):
        raise ValueError("Config JSON must be an object")
    return dict(raw)


def _resolve_refs(value: Any, *, base_dir: Path, chain: list[Path]) -> Any:
    if isinstance(value, list):
        return [_resolve_refs(item, base_dir=base_dir, chain=chain) for item in value]
    if not isinstance(value, Mapping):
        return value

    if "$ref" in value:
        ref = value.get("$ref")
        if not isinstance(ref, str) or not ref.strip():
            raise ValueError("Invalid $ref value")
        ref_path = (base_dir / ref).resolve()
        if ref_path in chain:
            raise ValueError(f"Cyclic $ref detected: {ref_path}")
        ref_raw = loads_jsonc(ref_path.read_text(encoding="utf-8"))
        resolved_ref = _resolve_refs(
            ref_raw, base_dir=ref_path.parent, chain=[*chain, ref_path]
        )
        if not isinstance(resolved_ref, Mapping):
            raise ValueError(f"$ref target must be an object: {ref}")
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
