"""Build the frozen, star-grouped Stage 2 LEGACY partition and integrity seal."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from collections import Counter, defaultdict
from collections.abc import Mapping, Sequence
from pathlib import Path

from topoastero.provenance import sha256_file

ROOT = Path(__file__).parents[1]
RUDY = "KIC 10963065"
SEED = 20260721
FROZEN_ON = "2026-09-20"
ALGORITHM_ID = "TA-GROUPED-STRATIFIED-SHA256-v1"
ROLE_FRACTIONS = {
    "development": 0.60,
    "internal_validation": 0.20,
    "final_holdout": 0.20,
}
FIELDS = [
    "assignment_id",
    "stable_star_id",
    "kic",
    "role",
    "group_key",
    "stratum",
    "numax_bin",
    "teff_bin",
    "assignment_rank",
    "algorithm_id",
    "master_seed",
    "source_row_sha256",
    "frozen_on",
]


def _row_hash(row: Mapping[str, str]) -> str:
    payload = json.dumps(dict(row), sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(payload).hexdigest()


def _seeded_key(stratum: str, stable_star_id: str) -> str:
    payload = f"TopoAstero|{SEED}|{stratum}|{stable_star_id}".encode()
    return hashlib.sha256(payload).hexdigest()


def _rank_bins(rows: Sequence[dict[str, str]], field: str) -> dict[str, str]:
    labels = ("low", "middle", "high")
    ordered = sorted(rows, key=lambda row: (float(row[field]), int(row["kic"])))
    size = len(ordered)
    return {
        row["object_id"]: labels[min(2, index * 3 // size)]
        for index, row in enumerate(ordered)
    }


def _global_targets(size: int) -> dict[str, int]:
    floors = {role: math.floor(fraction * size) for role, fraction in ROLE_FRACTIONS.items()}
    remaining = size - sum(floors.values())
    ranked = sorted(
        ROLE_FRACTIONS,
        key=lambda role: (-(ROLE_FRACTIONS[role] * size - floors[role]), role),
    )
    for role in ranked[:remaining]:
        floors[role] += 1
    return floors


def _stratum_quotas(sizes: Mapping[str, int]) -> dict[str, dict[str, int]]:
    targets = _global_targets(sum(sizes.values()))
    quotas = {
        stratum: {
            role: math.floor(fraction * size) for role, fraction in ROLE_FRACTIONS.items()
        }
        for stratum, size in sizes.items()
    }
    deficits = {
        role: targets[role] - sum(quotas[stratum][role] for stratum in quotas)
        for role in ROLE_FRACTIONS
    }
    while sum(deficits.values()) > 0:
        candidates: list[tuple[float, str, str]] = []
        for stratum, size in sorted(sizes.items()):
            if sum(quotas[stratum].values()) >= size:
                continue
            for role, fraction in ROLE_FRACTIONS.items():
                if deficits[role] <= 0:
                    continue
                remainder = fraction * size - quotas[stratum][role]
                candidates.append((-remainder, role, stratum))
        if not candidates:
            raise RuntimeError("unable to allocate stratified quotas")
        _, role, stratum = min(candidates)
        quotas[stratum][role] += 1
        deficits[role] -= 1
    return quotas


def build_assignments(source: Path) -> list[dict[str, str | int]]:
    with source.open(encoding="utf-8", newline="") as handle:
        population = list(csv.DictReader(handle))
    if len(population) != 66:
        raise ValueError(f"expected 66 LEGACY stars; found {len(population)}")
    analysis_rows = [row for row in population if row["object_id"] != RUDY]
    numax_bins = _rank_bins(analysis_rows, "numax_uHz")
    teff_bins = _rank_bins(analysis_rows, "teff_K")
    strata: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in analysis_rows:
        strata[numax_bins[row["object_id"]]].append(row)
    quotas = _stratum_quotas({key: len(value) for key, value in strata.items()})
    assigned: dict[str, tuple[str, int]] = {}
    for stratum in sorted(strata):
        ordered = sorted(
            strata[stratum], key=lambda row: _seeded_key(stratum, row["object_id"])
        )
        cursor = 0
        for role in ROLE_FRACTIONS:
            count = quotas[stratum][role]
            for rank, row in enumerate(ordered[cursor : cursor + count], start=cursor):
                assigned[row["object_id"]] = (role, rank)
            cursor += count
        if cursor != len(ordered):
            raise RuntimeError(f"quota error for stratum {stratum}")

    records: list[dict[str, str | int]] = []
    for index, row in enumerate(sorted(population, key=lambda item: int(item["kic"])), start=1):
        object_id = row["object_id"]
        if object_id == RUDY:
            role, rank = "descriptive_benchmark", 0
            numax_bin = teff_bin = stratum = "benchmark"
        else:
            role, rank = assigned[object_id]
            numax_bin = numax_bins[object_id]
            teff_bin = teff_bins[object_id]
            stratum = f"numax_{numax_bin}"
        records.append(
            {
                "assignment_id": f"SPLIT-{index:03d}",
                "stable_star_id": object_id,
                "kic": row["kic"],
                "role": role,
                "group_key": "stable_star_id",
                "stratum": stratum,
                "numax_bin": numax_bin,
                "teff_bin": teff_bin,
                "assignment_rank": rank,
                "algorithm_id": ALGORITHM_ID,
                "master_seed": SEED,
                "source_row_sha256": _row_hash(row),
                "frozen_on": FROZEN_ON,
            }
        )
    return records


def _write_csv(path: Path, records: Sequence[Mapping[str, str | int]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(records)


def main(argv: Sequence[str] | None = None) -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", default="evidence/benchmarks/legacy_population.csv")
    parser.add_argument("--output", default="registries/population_partitions.csv")
    parser.add_argument("--attestation", default="registries/split_attestation.json")
    parser.add_argument("--balance-report", default="reports/stage2/partition_balance.json")
    args = parser.parse_args(argv)
    source = ROOT / args.source
    output = ROOT / args.output
    records = build_assignments(source)
    _write_csv(output, records)
    role_counts = Counter(str(row["role"]) for row in records)
    cross_counts = Counter(
        (str(row["numax_bin"]), str(row["role"]))
        for row in records
        if row["role"] != "descriptive_benchmark"
    )
    attestation = {
        "schema_version": 1,
        "attestation_id": "TA-SPLIT-SEAL-20260920",
        "file": args.output,
        "sha256": sha256_file(output),
        "algorithm_id": ALGORITHM_ID,
        "master_seed": SEED,
        "source": args.source,
        "source_sha256": sha256_file(source),
        "frozen_on": FROZEN_ON,
        "signatory_role": "automated_data_steward",
        "integrity_mechanism": "SHA-256 content seal verified by validate-stage2",
        "holdout_access_state": "unopened_for_analysis",
    }
    attestation_path = ROOT / args.attestation
    attestation_path.write_text(
        json.dumps(attestation, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    balance = {
        "schema_version": 1,
        "population_rows": len(records),
        "analysis_rows": len(records) - role_counts["descriptive_benchmark"],
        "role_counts": dict(sorted(role_counts.items())),
        "numax_bin_by_role": {
            f"{bin_name}:{role}": count
            for (bin_name, role), count in sorted(cross_counts.items())
        },
        "stratification": (
            "Assignment used label-free nu_max rank tertiles; Teff tertiles are recorded as "
            "a balance diagnostic and no topology-derived value was inspected."
        ),
    }
    balance_path = ROOT / args.balance_report
    balance_path.parent.mkdir(parents=True, exist_ok=True)
    balance_path.write_text(json.dumps(balance, indent=2, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
