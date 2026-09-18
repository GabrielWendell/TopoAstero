"""Provenance helpers shared by workflows and reports."""

from __future__ import annotations

import hashlib
import os
import platform
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


def sha256_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def derive_seed(master_seed: int, namespace: str, replicate: int) -> int:
    """Derive a scheduling-independent unsigned 64-bit child seed."""

    if master_seed < 0 or replicate < 0:
        raise ValueError("master_seed and replicate must be nonnegative")
    if not namespace.strip():
        raise ValueError("namespace must be non-empty")
    payload = f"TopoAstero|{master_seed}|{namespace}|{replicate}".encode()
    return int.from_bytes(hashlib.sha256(payload).digest()[:8], byteorder="big", signed=False)


def utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def git_state(root: str | Path) -> dict[str, str | bool | None]:
    repository = Path(root)

    def run(*arguments: str) -> str | None:
        try:
            completed = subprocess.run(
                ["git", *arguments],
                cwd=repository,
                check=True,
                capture_output=True,
                text=True,
            )
        except (OSError, subprocess.CalledProcessError):
            return None
        return completed.stdout.strip()

    commit = run("rev-parse", "HEAD")
    status = run("status", "--porcelain")
    return {
        "commit": commit,
        "dirty": bool(status) if status is not None else None,
        "describe": run("describe", "--always", "--dirty", "--tags"),
    }


def environment_snapshot() -> dict[str, Any]:
    return {
        "captured_at_utc": utc_now(),
        "python": sys.version.split()[0],
        "implementation": platform.python_implementation(),
        "platform": platform.platform(),
        "machine": platform.machine(),
        "processor": platform.processor() or None,
        "cpu_count": os.cpu_count(),
    }
