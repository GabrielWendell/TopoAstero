from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from topoastero.provenance import derive_seed, environment_snapshot, git_state, sha256_file, utc_now


def test_file_hash_and_seed_derivation(tmp_path: Path) -> None:
    path = tmp_path / "payload.bin"
    path.write_bytes(b"topoastero")
    assert sha256_file(path) == hashlib.sha256(b"topoastero").hexdigest()
    assert derive_seed(12, "simulation", 3) == derive_seed(12, "simulation", 3)
    assert derive_seed(12, "simulation", 3) != derive_seed(12, "simulation", 4)
    with pytest.raises(ValueError):
        derive_seed(-1, "simulation", 0)
    with pytest.raises(ValueError):
        derive_seed(1, "", 0)


def test_environment_and_git_snapshots_are_structured(tmp_path: Path) -> None:
    environment = environment_snapshot()
    assert environment["python"]
    assert environment["cpu_count"]
    assert utc_now().endswith("+00:00")
    missing_git = git_state(tmp_path)
    assert missing_git["commit"] is None
    assert missing_git["dirty"] is None

