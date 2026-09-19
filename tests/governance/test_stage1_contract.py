from __future__ import annotations

import json
from pathlib import Path

import pytest

from topoastero.evidence import bibtex_keys, read_csv_rows
from topoastero.stage1_validation import _decimal, _require_fields, _unique, validate_stage1

ROOT = Path(__file__).parents[2]


@pytest.mark.governance
def test_complete_stage1_contract() -> None:
    assert validate_stage1(ROOT, require_stage0=True) == []


@pytest.mark.governance
def test_benchmark_cardinality_and_authority() -> None:
    benchmark_dir = ROOT / "evidence/benchmarks"
    population = read_csv_rows(benchmark_dir / "legacy_population.csv")
    targets = read_csv_rows(benchmark_dir / "benchmark_targets.csv")
    modes = read_csv_rows(benchmark_dir / "rudy_mode_frequencies.csv")
    assert len(population) == 66
    assert len([row for row in targets if row["status"] == "benchmark"]) == 264
    assert len([row for row in targets if row["status"] == "context_only"]) == 12
    assert len(modes) == 42
    rudy = {
        row["quantity"]: row["value"]
        for row in targets
        if row["object_id"] == "KIC 10963065" and row["status"] == "benchmark"
    }
    assert rudy["numax"] == "2203.7"
    assert rudy["dnu"] == "103.179"


@pytest.mark.governance
def test_reference_and_gate_records_agree() -> None:
    audit = read_csv_rows(ROOT / "evidence/references/reference_audit.csv")
    keys = bibtex_keys(ROOT / "evidence/references/topoastero_stage1.bib")
    assert {row["source_key"] for row in audit} == keys
    assert len(keys) == 35
    gate = json.loads((ROOT / "reports/stage1/G1_ACCEPTANCE.json").read_text(encoding="utf-8"))
    assert gate["decision"] == "PASS"
    assert all(clause["status"] == "pass" for clause in gate["clauses"])


def test_stage1_validation_helpers_report_bad_records() -> None:
    errors: list[str] = []
    _require_fields([], {"id"}, "empty", errors)
    _require_fields([{"id": "", "extra": "x"}], {"id"}, "bad fields", errors)
    assert _decimal("not-a-number", "quantity", errors) is None
    _unique([{"id": "x"}, {"id": "x"}], "id", "records", errors)
    assert any("at least one row" in error for error in errors)
    assert any("fields differ" in error for error in errors)
    assert any("not numeric" in error for error in errors)
    assert any("duplicate" in error for error in errors)
