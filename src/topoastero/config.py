"""Configuration loading and content-addressed hashing."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import yaml  # type: ignore[import-untyped]


class ConfigError(ValueError):
    """Raised when a configuration is missing or structurally invalid."""


def load_yaml(path: str | Path) -> dict[str, Any]:
    """Load a YAML mapping using the safe loader."""

    config_path = Path(path)
    if not config_path.is_file():
        raise ConfigError(f"Configuration does not exist: {config_path}")
    with config_path.open("r", encoding="utf-8") as handle:
        value = yaml.safe_load(handle)
    if not isinstance(value, dict):
        raise ConfigError(f"Expected a YAML mapping in {config_path}")
    return value


def canonical_json(value: Any) -> str:
    """Return the canonical JSON representation used by every registry hash."""

    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def content_hash(value: Any) -> str:
    """Hash a JSON-compatible value with SHA-256."""

    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def configuration_hash(path: str | Path) -> str:
    """Hash the parsed configuration rather than its incidental YAML formatting."""

    return content_hash(load_yaml(path))

