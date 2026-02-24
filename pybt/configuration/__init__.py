"""Configuration and schema definitions for PyBT."""

from .definitions import ComponentDef, ParamDef, iter_definition_dicts, list_definitions
from .config_file import load_config_dict, load_config_file, loads_jsonc, resolve_config_refs
from .loader import load_engine_from_dict, load_engine_from_json
from .plugins import PluginConfigError, PluginLoader, PluginRegistry
from .user_env import default_user_config_path, ensure_user_config

__all__ = [
    "ComponentDef",
    "ParamDef",
    "iter_definition_dicts",
    "list_definitions",
    "load_config_file",
    "load_config_dict",
    "loads_jsonc",
    "resolve_config_refs",
    "load_engine_from_dict",
    "load_engine_from_json",
    "PluginRegistry",
    "PluginLoader",
    "PluginConfigError",
    "default_user_config_path",
    "ensure_user_config",
]
