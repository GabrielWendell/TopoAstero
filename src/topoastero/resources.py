"""Portable resource inventory and small persistence benchmark."""

from __future__ import annotations

import importlib.metadata
import os
import platform
import shutil
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from topoastero.persistence import superlevel_h0
from topoastero.provenance import utc_now
from topoastero.render import write_json
from topoastero.simulation import deterministic_multimode_signal


def _memory_bytes() -> int | None:
    if not Path("/proc/meminfo").is_file():
        return None
    for line in Path("/proc/meminfo").read_text(encoding="utf-8").splitlines():
        if line.startswith("MemTotal:"):
            return int(line.split()[1]) * 1024
    return None


def _distribution_record(name: str) -> dict[str, str | None]:
    licenses = {"TopoAstero": "BSD-3-Clause", "PyYAML": "MIT"}
    try:
        return {
            "name": name,
            "version": importlib.metadata.version(name),
            "license": licenses.get(name),
        }
    except importlib.metadata.PackageNotFoundError:
        return {"name": name, "version": None, "license": None}


def _archive_probe(enabled: bool) -> dict[str, str | int | bool | None]:
    url = "https://mast.stsci.edu/portal/Mashup/Clients/Mast/Portal.html"
    if not enabled:
        return {"url": url, "attempted": False, "reachable": None, "status": "offline_mode"}
    try:
        request = urllib.request.Request(url, headers={"User-Agent": "TopoAstero/0.1"})
        with urllib.request.urlopen(request, timeout=8) as response:
            return {
                "url": url,
                "attempted": True,
                "reachable": response.status == 200,
                "http_status": response.status,
                "status": "verified" if response.status == 200 else "unexpected_status",
            }
    except (urllib.error.URLError, TimeoutError) as error:
        return {
            "url": url,
            "attempted": True,
            "reachable": False,
            "http_status": None,
            "status": f"probe_failed:{type(error).__name__}",
        }


def audit_resources(root: str | Path, *, check_network: bool) -> dict[str, Any]:
    repository = Path(root).resolve()
    disk = shutil.disk_usage(repository)
    _, values = deterministic_multimode_signal(
        samples=512,
        seed=20260721,
        fundamental_cycles=5.0,
        secondary_cycles=11.0,
        secondary_amplitude=0.35,
        noise_sigma=0.02,
    )
    repeats = 100
    start = time.perf_counter()
    pair_count = 0
    for _ in range(repeats):
        pair_count = len(superlevel_h0(values))
    elapsed = time.perf_counter() - start
    resolved_commands = {
        name: shutil.which(name)
        for name in ("git", "uv", "python", "mesa", "star", "gyre", "docker", "apptainer")
    }
    commands = {name: path is not None for name, path in resolved_commands.items()}
    return {
        "audit_version": 1,
        "captured_at_utc": utc_now(),
        "host": {
            "platform": platform.platform(),
            "machine": platform.machine(),
            "python": sys.version.split()[0],
            "logical_cpu_count": os.cpu_count(),
            "memory_bytes": _memory_bytes(),
            "storage": {
                "path": repository.name,
                "total_bytes": disk.total,
                "free_bytes": disk.free,
            },
        },
        "software": {
            "commands": commands,
            "python_distributions": [
                _distribution_record(name) for name in ("TopoAstero", "PyYAML")
            ],
            "mesa_capability": (
                "available"
                if resolved_commands["star"] or resolved_commands["mesa"]
                else "not_detected"
            ),
            "gyre_capability": "available" if commands["gyre"] else "not_detected",
        },
        "archive_access": _archive_probe(check_network),
        "persistence_benchmark": {
            "algorithm": "exact_superlevel_h0_path",
            "samples": len(values),
            "repeats": repeats,
            "pairs_last_run": pair_count,
            "total_seconds": elapsed,
            "seconds_per_run": elapsed / repeats,
        },
        "planning_targets": {
            "cpu_hours": "50000-100000 for the full publication program; replace after S4 profiling",
            "temporary_storage_tb": "2-5",
            "archival_derived_gb_max": 200,
            "gpu_required_for_core": False,
        },
    }


def write_resource_audit(root: str | Path, output: str | Path, *, check_network: bool) -> dict[str, Any]:
    record = audit_resources(root, check_network=check_network)
    write_json(output, record)
    return record
