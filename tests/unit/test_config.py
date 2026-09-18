from __future__ import annotations

from pathlib import Path

import pytest

from topoastero.config import (
    ConfigError,
    canonical_json,
    configuration_hash,
    content_hash,
    load_yaml,
)


def test_canonical_hash_is_key_order_invariant() -> None:
    left = {"b": [2, 1], "a": {"x": True}}
    right = {"a": {"x": True}, "b": [2, 1]}
    assert canonical_json(left) == canonical_json(right)
    assert content_hash(left) == content_hash(right)
    assert content_hash(left) != content_hash({"b": [1, 2], "a": {"x": True}})


def test_load_and_hash_yaml(tmp_path: Path) -> None:
    path = tmp_path / "config.yaml"
    path.write_text("b: 2\na: 1\n", encoding="utf-8")
    assert load_yaml(path) == {"a": 1, "b": 2}
    first = configuration_hash(path)
    path.write_text("a: 1\nb: 2\n", encoding="utf-8")
    assert configuration_hash(path) == first


def test_load_yaml_rejects_missing_or_non_mapping(tmp_path: Path) -> None:
    with pytest.raises(ConfigError, match="does not exist"):
        load_yaml(tmp_path / "missing.yaml")
    path = tmp_path / "list.yaml"
    path.write_text("- one\n- two\n", encoding="utf-8")
    with pytest.raises(ConfigError, match="mapping"):
        load_yaml(path)

