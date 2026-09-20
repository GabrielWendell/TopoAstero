"""Build canonical Stage 2 reference tables from checked Stage 1 evidence."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
from collections.abc import Mapping, Sequence
from pathlib import Path

from topoastero.config import configuration_hash
from topoastero.provenance import sha256_file

ROOT = Path(__file__).parents[1]
RUDY_KIC = "10963065"
TABLE7_SHA256 = "26bb32a8eb02d03d2aa3d270625ac96d5720ba667312d814b7f291cb38c8b39f"
TABLE7_URL = (
    "https://content.cld.iop.org/journals/0004-637X/835/2/172/revision1/"
    "apjaa5593t7_mrt.txt"
)


def _write_csv(path: Path, rows: Sequence[Mapping[str, str]]) -> None:
    if not rows:
        raise ValueError(f"refusing to write empty table: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def _source_row_id(path: Path, row: Mapping[str, str]) -> str:
    payload = json.dumps(dict(row), sort_keys=True, separators=(",", ":")).encode()
    return f"{path.name}:{hashlib.sha256(payload).hexdigest()[:16]}"


def build_mode_references(config_hash: str) -> list[dict[str, str]]:
    source = ROOT / "evidence/benchmarks/rudy_mode_frequencies.csv"
    with source.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    return [
        {
            "row_id": f"MODE-RUDY-{index:03d}",
            "stable_star_id": row["object_id"],
            "radial_order_n": row["radial_order_n"],
            "angular_degree_l": row["angular_degree_l"],
            "frequency_uHz": row["frequency_uHz"],
            "uncertainty_minus_uHz": row["frequency_error_minus_uHz"],
            "uncertainty_plus_uHz": row["frequency_error_plus_uHz"],
            "source_id": "Lund2017-Table6",
            "source_version": "publisher-revision1",
            "raw_product_ids": "SRC-B03",
            "source_row_ids": _source_row_id(source, row),
            "config_sha256": config_hash,
            "software_version": "TopoAstero-0.3.0",
        }
        for index, row in enumerate(rows, start=1)
    ]


def build_stellar_references(config_hash: str) -> list[dict[str, str]]:
    source = ROOT / "evidence/benchmarks/benchmark_targets.csv"
    with source.open(encoding="utf-8", newline="") as handle:
        rows = [row for row in csv.DictReader(handle) if row["status"] == "benchmark"]
    return [
        {
            "row_id": row["benchmark_id"],
            "stable_star_id": row["object_id"],
            "quantity": row["quantity"],
            "value": row["value"],
            "unit": row["unit"],
            "uncertainty_minus": row["uncertainty_minus"],
            "uncertainty_plus": row["uncertainty_plus"],
            "uncertainty_type": row["uncertainty_type"],
            "method": row["method"],
            "source_id": f"{row['source_key']}-Table3",
            "source_version": "publisher-revision1",
            "raw_product_ids": "SRC-B01",
            "source_row_ids": _source_row_id(source, row),
            "config_sha256": config_hash,
            "software_version": "TopoAstero-0.3.0",
        }
        for row in rows
    ]


def build_ratios(table: Path, config_hash: str) -> list[dict[str, str]]:
    if sha256_file(table) != TABLE7_SHA256:
        raise ValueError("Table 7 SHA-256 does not match the frozen source record")
    rows: list[dict[str, str]] = []
    for line in table.read_text(encoding="utf-8").splitlines():
        fields = line.split()
        if len(fields) != 6 or fields[0] != RUDY_KIC:
            continue
        _, ratio_type, radial_order, value, lower, upper = fields
        if re.fullmatch(r"r_(?:01|10|02)_", ratio_type) is None:
            continue
        rows.append(
            {
                "row_id": f"RATIO-RUDY-{len(rows) + 1:03d}",
                "stable_star_id": f"KIC {RUDY_KIC}",
                "ratio_type": ratio_type.strip("_"),
                "radial_order_n": radial_order,
                "value": value,
                "uncertainty_minus": lower,
                "uncertainty_plus": upper,
                "unit": "dimensionless",
                "source_id": "Lund2017-Table7",
                "source_version": "publisher-revision1",
                "raw_product_ids": "SRC-B05",
                "source_row_ids": f"apjaa5593t7_mrt.txt:line-{len(rows) + 1:04d}",
                "config_sha256": config_hash,
                "software_version": "TopoAstero-0.3.0",
            }
        )
    if len(rows) != 38:
        raise ValueError(f"expected 38 Rudy frequency-ratio rows; found {len(rows)}")
    return rows


def write_reference_manifest(output: Path, table7: Path) -> None:
    paths = [
        ROOT / "data/reference/mode_frequencies.csv",
        ROOT / "data/reference/stellar_references.csv",
        ROOT / "data/reference/frequency_ratios.csv",
    ]
    rows = [
        {
            "reference_id": f"REF-{index:02d}",
            "path": str(path.relative_to(ROOT)),
            "rows": str(sum(1 for _ in path.open(encoding="utf-8")) - 1),
            "size_bytes": str(path.stat().st_size),
            "sha256": sha256_file(path),
            "source_version": "TopoAstero-0.3.0",
        }
        for index, path in enumerate(paths, start=1)
    ]
    _write_csv(output, rows)
    sources = [
        {
            "source_id": "SRC-B05",
            "artifact": "Lund et al. 2017 publisher machine-readable Table 7",
            "url": TABLE7_URL,
            "retrieved_on": "2026-09-20",
            "sha256": sha256_file(table7),
            "redistribution": "raw publisher payload not redistributed",
            "derived_use": "data/reference/frequency_ratios.csv",
        },
        {
            "source_id": "STAGE1-MODES",
            "artifact": "Stage 1 checked Rudy mode table",
            "url": "evidence/benchmarks/rudy_mode_frequencies.csv",
            "retrieved_on": "2026-09-20",
            "sha256": sha256_file(ROOT / "evidence/benchmarks/rudy_mode_frequencies.csv"),
            "redistribution": "project-authored derived table",
            "derived_use": "data/reference/mode_frequencies.csv",
        },
        {
            "source_id": "STAGE1-TARGETS",
            "artifact": "Stage 1 checked LEGACY target table",
            "url": "evidence/benchmarks/benchmark_targets.csv",
            "retrieved_on": "2026-09-20",
            "sha256": sha256_file(ROOT / "evidence/benchmarks/benchmark_targets.csv"),
            "redistribution": "project-authored derived table",
            "derived_use": "data/reference/stellar_references.csv",
        },
    ]
    _write_csv(ROOT / "data/manifests/stage2/reference_sources.csv", sources)


def main(argv: Sequence[str] | None = None) -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--table7", required=True)
    args = parser.parse_args(argv)
    config_hash = configuration_hash(ROOT / "configs/stage2_data.yaml")
    _write_csv(
        ROOT / "data/reference/mode_frequencies.csv", build_mode_references(config_hash)
    )
    _write_csv(
        ROOT / "data/reference/stellar_references.csv", build_stellar_references(config_hash)
    )
    table7 = Path(args.table7)
    _write_csv(ROOT / "data/reference/frequency_ratios.csv", build_ratios(table7, config_hash))
    write_reference_manifest(ROOT / "data/manifests/stage2/reference_manifest.csv", table7)


if __name__ == "__main__":
    main()
