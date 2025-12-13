from ..models import DefinitionItem, DefinitionParam

from pybt.definitions import list_definitions as _list_pybt_definitions


def list_definitions() -> list[DefinitionItem]:
    """Return supported component types for form auto-generation.

    This is sourced from `pybt.definitions` to ensure the backend stays in sync
    with the config loader (`pybt.config`).
    """

    items: list[DefinitionItem] = []
    for definition in _list_pybt_definitions():
        params = [
            DefinitionParam(
                name=param.name,
                type=param.type,
                required=param.required,
                default=param.default,
                description=param.description,
            )
            for param in definition.params
        ]
        items.append(
            DefinitionItem(
                category=definition.category,
                type=definition.type,
                summary=definition.summary,
                params=params,
            )
        )
    return items
