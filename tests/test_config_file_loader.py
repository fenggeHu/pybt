from pathlib import Path

import pytest

from pybt.configuration.config_file import load_config_dict, loads_jsonc


def test_loads_jsonc_supports_comments_and_trailing_commas() -> None:
    data = loads_jsonc(
        """
        {
          // line comment
          "name": "demo",
          "items": [1, 2,],
          /* block comment */
          "enabled": true,
        }
        """
    )
    assert data["name"] == "demo"
    assert data["items"] == [1, 2]
    assert data["enabled"] is True


def test_load_config_dict_resolves_local_refs(tmp_path: Path) -> None:
    (tmp_path / "base.jsonc").write_text(
        """
        {
          "type": "moving_average",
          "symbol": "AAA",
          "short_window": 5,
          "long_window": 20,
        }
        """,
        encoding="utf-8",
    )
    (tmp_path / "profile.jsonc").write_text(
        """
        {
          "strategy": {
            "$ref": "./base.jsonc",
            "short_window": 3
          }
        }
        """,
        encoding="utf-8",
    )

    cfg = load_config_dict(tmp_path / "profile.jsonc")
    assert cfg["strategy"]["short_window"] == 3
    assert cfg["strategy"]["long_window"] == 20


def test_load_config_dict_detects_ref_cycle(tmp_path: Path) -> None:
    (tmp_path / "a.jsonc").write_text('{"$ref":"./b.jsonc"}', encoding="utf-8")
    (tmp_path / "b.jsonc").write_text('{"$ref":"./a.jsonc"}', encoding="utf-8")

    with pytest.raises(ValueError, match="Cyclic \\$ref"):
        load_config_dict(tmp_path / "a.jsonc")
