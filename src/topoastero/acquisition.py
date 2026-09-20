"""Offline verification helpers for externally cached mission payloads."""

from __future__ import annotations

import csv
from collections import defaultdict
from collections.abc import Iterable
from pathlib import Path

from topoastero.provenance import sha256_file


def read_product_manifest(path: str | Path) -> list[dict[str, str]]:
    """Read a Stage 2 mission-product CSV without changing field text."""
    with Path(path).open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def index_cache(cache_dir: str | Path) -> tuple[dict[str, Path], set[str]]:
    """Index payloads by basename and expose ambiguous duplicate names."""
    candidates: dict[str, list[Path]] = defaultdict(list)
    root = Path(cache_dir)
    if not root.is_dir():
        return {}, set()
    for path in root.rglob("*"):
        if path.is_file() and not path.name.endswith(".part"):
            candidates[path.name].append(path)
    duplicates = {name for name, paths in candidates.items() if len(paths) > 1}
    return {name: paths[0] for name, paths in candidates.items()}, duplicates


def verify_cached_products(
    manifests: Iterable[str | Path], cache_dir: str | Path
) -> list[str]:
    """Check filename, byte size, and SHA-256 for every manifest row."""
    files, duplicate_names = index_cache(cache_dir)
    errors: list[str] = []
    for manifest in manifests:
        for row in read_product_manifest(manifest):
            key = row.get("product_key", "<missing>")
            filename = row.get("product_filename", "")
            if filename in duplicate_names:
                errors.append(f"{key}: cache contains duplicate basename {filename}")
                continue
            path = files.get(filename)
            if path is None:
                errors.append(f"{key}: payload missing from cache: {filename}")
                continue
            try:
                expected_size = int(row["size_bytes"])
            except (KeyError, ValueError):
                errors.append(f"{key}: invalid size_bytes")
                continue
            if path.stat().st_size != expected_size:
                errors.append(
                    f"{key}: size mismatch ({path.stat().st_size} != {expected_size})"
                )
                continue
            actual_hash = sha256_file(path)
            if actual_hash != row.get("sha256"):
                errors.append(f"{key}: SHA-256 mismatch")
    return errors
