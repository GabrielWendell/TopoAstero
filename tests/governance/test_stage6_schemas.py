from __future__ import annotations

import csv
import json
from pathlib import Path

from jsonschema import Draft202012Validator

ROOT = Path(__file__).parents[2]


def _schema(name: str) -> dict[str, object]:
    value = json.loads((ROOT / "schemas" / name).read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(value)
    return value


def test_localized_peak_records_validate() -> None:
    schema = _schema("psd_persistence_pair.schema.json")
    payload = json.loads((ROOT / "results/stage6/peak_diagram.json").read_text())
    for record in payload["pairs"]:
        Draft202012Validator(schema).validate(record)


def test_numax_and_comb_records_validate() -> None:
    numax_schema = _schema("numax_estimate.schema.json")
    with (ROOT / "results/stage6/numax_benchmark.csv").open(newline="") as handle:
        row = next(row for row in csv.DictReader(handle) if row["method"] == "persistence_centroid")
    record = {
        "numax_uHz": float(row["estimate_uHz"]),
        "lower_uHz": float(row["lower_uHz"]),
        "upper_uHz": float(row["upper_uHz"]),
        "interval_level": 0.95,
        "method": "centroid",
        "effective_peak_count": 1.0,
        "finite_peak_count": 1,
        "detection_statistic": 0.0,
        "bootstrap_replicates": 48,
    }
    Draft202012Validator(numax_schema).validate(record)

    comb_schema = _schema("comb_candidate.schema.json")
    with (ROOT / "results/stage6/comb_candidates.csv").open(newline="") as handle:
        rows = list(csv.DictReader(handle))
    for row in rows:
        record = {
            "alias": row["alias"],
            "spacing_uHz": float(row["spacing_uHz"]),
            "difference_score": float(row["difference_score"]),
            "autocorrelation_score": float(row["autocorrelation_score"]),
            "combined_score": float(row["combined_score"]),
            "rank": int(row["rank"]),
        }
        Draft202012Validator(comb_schema).validate(record)


def test_quality_records_validate() -> None:
    schema = _schema("spectral_quality.schema.json")
    with (ROOT / "results/stage6/quality_flags.csv").open(newline="") as handle:
        rows = list(csv.DictReader(handle))
    for row in rows:
        Draft202012Validator(schema).validate(
            {
                "cell_id": row["cell_id"],
                "flags": json.loads(row["flags_json"]),
                "status": row["status"],
                "reliable": row["reliable"] == "true",
            }
        )


def test_stage6_run_manifest_validates() -> None:
    schema = _schema("stage6_run_manifest.schema.json")
    manifest = json.loads((ROOT / "results/stage6/run_manifest.json").read_text())
    Draft202012Validator(schema).validate(manifest)

