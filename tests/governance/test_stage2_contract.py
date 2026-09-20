from __future__ import annotations

import csv
import json
from collections import Counter
from pathlib import Path

import pytest

from topoastero.stage2_validation import validate_stage2

ROOT = Path(__file__).parents[2]


def rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


@pytest.mark.governance
def test_complete_stage2_contract() -> None:
    assert validate_stage2(ROOT, require_prior_stages=True) == []


@pytest.mark.governance
def test_mission_and_reference_cardinality() -> None:
    manifests = ROOT / "data/manifests/stage2"
    assert len(rows(manifests / "rudy_kepler_products.csv")) == 10
    tess = rows(manifests / "rudy_tess_products.csv")
    assert len(tess) == 33
    assert Counter(row["author"] for row in tess) == {"SPOC": 11, "TESS-SPOC": 11, "QLP": 11}
    assert len(rows(ROOT / "data/reference/mode_frequencies.csv")) == 42
    assert len(rows(ROOT / "data/reference/frequency_ratios.csv")) == 38
    assert len(rows(ROOT / "data/reference/stellar_references.csv")) == 264


@pytest.mark.governance
def test_partition_is_grouped_and_sealed() -> None:
    partitions = rows(ROOT / "registries/population_partitions.csv")
    assert len(partitions) == len({row["stable_star_id"] for row in partitions}) == 66
    assert Counter(row["role"] for row in partitions) == {
        "development": 39,
        "internal_validation": 13,
        "final_holdout": 13,
        "descriptive_benchmark": 1,
    }
    rudy = next(row for row in partitions if row["stable_star_id"] == "KIC 10963065")
    assert rudy["role"] == "descriptive_benchmark"
    gate = json.loads((ROOT / "reports/stage2/G2_ACCEPTANCE.json").read_text())
    assert gate["decision"] == "PASS"
    assert all(clause["status"] == "pass" for clause in gate["clauses"])
