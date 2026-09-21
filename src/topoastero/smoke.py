"""End-to-end deterministic Stage 0 smoke workflow."""

from __future__ import annotations

import time as clock
from pathlib import Path
from typing import Any

from topoastero import __version__
from topoastero.config import configuration_hash, content_hash, load_yaml
from topoastero.persistence import PersistencePair, superlevel_h0
from topoastero.portability import repository_relative_posix
from topoastero.provenance import environment_snapshot, git_state, sha256_file, utc_now
from topoastero.render import write_json, write_rows, write_smoke_svg
from topoastero.simulation import deterministic_multimode_signal


def _required_mapping(config: dict[str, Any], key: str) -> dict[str, Any]:
    value = config.get(key)
    if not isinstance(value, dict):
        raise ValueError(f"Configuration field '{key}' must be a mapping")
    return value


def run_smoke(config_path: str | Path, output_dir: str | Path) -> dict[str, Any]:
    """Run a small, seeded persistence calculation and write auditable outputs."""

    config_file = Path(config_path).resolve()
    repository_root = config_file.parents[1]
    output = Path(output_dir).resolve()
    output.mkdir(parents=True, exist_ok=True)
    config = load_yaml(config_file)
    signal_config = _required_mapping(config, "signal")
    persistence_config = _required_mapping(config, "persistence")
    benchmark_config = _required_mapping(config, "benchmark")

    time, signal = deterministic_multimode_signal(
        samples=int(signal_config["samples"]),
        seed=int(config["random_seed"]),
        fundamental_cycles=float(signal_config["fundamental_cycles"]),
        secondary_cycles=float(signal_config["secondary_cycles"]),
        secondary_amplitude=float(signal_config["secondary_amplitude"]),
        noise_sigma=float(signal_config["noise_sigma"]),
    )
    include_zero = bool(persistence_config.get("include_zero", False))
    pairs = superlevel_h0(signal, include_zero=include_zero)

    repeats = int(benchmark_config["repeats"])
    if repeats < 1:
        raise ValueError("benchmark.repeats must be positive")
    start = clock.perf_counter()
    for _ in range(repeats):
        superlevel_h0(signal, include_zero=include_zero)
    elapsed_seconds = clock.perf_counter() - start

    signal_rows = [
        {"sample": index, "time_normalized": f"{x:.17g}", "amplitude": f"{y:.17g}"}
        for index, (x, y) in enumerate(zip(time, signal, strict=True))
    ]
    pair_rows = [pair.to_dict() for pair in pairs]
    write_rows(
        output / "signal.csv",
        signal_rows,
        fields=["sample", "time_normalized", "amplitude"],
    )
    write_rows(
        output / "persistence_pairs.csv",
        pair_rows,
        fields=[
            "birth_index",
            "death_index",
            "birth",
            "death",
            "essential",
            "persistence",
        ],
    )
    write_smoke_svg(output / "smoke_figure.svg", time, signal, pairs)

    finite = [pair for pair in pairs if pair.persistence is not None]
    stable_payload = {
        "workflow": config["workflow_id"],
        "config_hash": configuration_hash(config_file),
        "random_seed": int(config["random_seed"]),
        "samples": len(signal),
        "finite_pair_count": len(finite),
        "essential_pair_count": sum(pair.essential for pair in pairs),
        "largest_finite_persistence": max(pair.persistence or 0.0 for pair in finite),
        "signal_hash": content_hash(signal),
        "pairs_hash": content_hash(pair_rows),
    }
    stable_payload["result_hash"] = content_hash(stable_payload)
    write_json(output / "summary.json", stable_payload)

    manifest = {
        "experiment_id": str(config["experiment_id"]),
        "hypothesis_id": str(config["hypothesis_id"]),
        "split_role": str(config["split_role"]),
        "status": "completed",
        "captured_at_utc": utc_now(),
        "package_version": __version__,
        "configuration": {
            "path": repository_relative_posix(config_file, repository_root),
            "sha256_canonical": stable_payload["config_hash"],
        },
        "code": git_state(repository_root),
        "environment": environment_snapshot(),
        "random_seeds": [int(config["random_seed"])],
        "benchmark": {
            "repeats": repeats,
            "total_seconds": elapsed_seconds,
            "seconds_per_run": elapsed_seconds / repeats,
        },
        "outputs": {},
        "result_hash": stable_payload["result_hash"],
    }
    for name in ("signal.csv", "persistence_pairs.csv", "summary.json", "smoke_figure.svg"):
        manifest["outputs"][name] = {"sha256": sha256_file(output / name)}
    write_json(output / "run_manifest.json", manifest)
    return {"summary": stable_payload, "manifest": manifest, "output_dir": str(output)}


def finite_pairs(pairs: list[PersistencePair]) -> list[PersistencePair]:
    """Convenience filter retained for downstream workflow composition."""

    return [pair for pair in pairs if not pair.essential]
