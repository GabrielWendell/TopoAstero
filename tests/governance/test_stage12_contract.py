"""Observed Stage 12 evidence contracts; no raw holdout access."""
from __future__ import annotations

from pathlib import Path

import jsonschema
import pytest

from topoastero.hybrid.features import CLASSICAL, TOPOLOGY, load_config
from topoastero.hybrid.validation import validate
from topoastero.population_store import read_json, read_table, seal_issues

ROOT = Path(__file__).parents[2]


@pytest.mark.governance
def test_stage12_schema_evidence_and_protected_confirmation() -> None:
    assert validate(ROOT) == []
    cfg = load_config(ROOT)
    gate = read_json(ROOT / cfg["reports"] / "G12_ACCEPTANCE.json")
    pack = read_json(ROOT / cfg["output"] / "models.json")
    jsonschema.validate(gate, read_json(ROOT / "schemas/stage12_gate.schema.json"))
    jsonschema.validate(pack, read_json(ROOT / "schemas/stage12_models.schema.json"))
    assert gate["status"] == "validation_pending" and gate["usable_development_stars"] == 9
    assert not gate["positive_complementarity_claim"] and not gate["publication_ready"]
    assert gate["confirmation_opening_count"] == 0 and not pack["holdout_used"]
    assert not (ROOT / cfg["release"]).exists() and not (ROOT / cfg["confirmation_state"]).exists()
    assert not (ROOT / "registries/stage11_confirmation.json").exists()


def test_feature_lock_tasks_and_complete_cohort_denominator() -> None:
    cfg = load_config(ROOT)
    tasks = read_table(ROOT / cfg["reports"] / "task_traceability.csv")
    assert {r["task_id"] for r in tasks} == {f"T12.{i}" for i in range(1, 12)}
    features = read_table(ROOT / "registries/stage12_features.csv")
    assert tuple(r["feature"] for r in features) == CLASSICAL + TOPOLOGY
    data = read_json(ROOT / cfg["output"] / "feature_dataset.json")
    assert len(data["ledger"]) == 39 and sum(r["included"] for r in data["ledger"]) == 9
    assert len({r["stable_star_id"] for r in data["rows"]}) == 9
    assert all(r["role"] == "development" and r["stable_star_id"] != "KIC 10963065" for r in data["rows"])
    audits = read_json(ROOT / cfg["output"] / "fold_audit.json")["folds"]
    assert all(not set(a["train_stars"]) & set(a["test_stars"]) for a in audits)
    probability = read_json(ROOT / cfg["output"] / "probability_calibration.json")["tasks"]
    assert all(t.get("Brier") is None for t in probability)
    assert all(r["metrics"]["baseline"]["interval_available"] == 0 for r in read_json(ROOT / cfg["output"] / "increment.json")["rows"])


def test_physical_benchmark_and_nondetections_remain_visible() -> None:
    cfg = load_config(ROOT)
    output = ROOT / cfg["output"]
    run = read_json(output / "transfer_run.json")
    assert run["cells"] == 192 and run["actual_sectors"] == 11 and run["parent_stars"] == 1
    assert run["model_frozen_before_actual"] and not run["actual_test_sectors_tuned"]
    assert not run["recalibration_applied"]
    assert len(list((output / "degraded").glob("*.npz"))) == 192
    assert seal_issues(ROOT, run["files"]) == []
    actual = read_json(output / "actual_tess.json")
    assert len(actual["rows"]) == 44 and len(actual["combinations"]) == 4
    assert len({r["sector"] for r in actual["rows"]}) == 11
    assert all(not r["accepted"] and r["estimate"] is None and r["failure_probability"] is None for r in actual["rows"])
    assert all(r["candidate_estimate"] is not None for r in actual["rows"])
    figures = read_json(ROOT / cfg["reports"] / "figure_manifest.json")["figures"]
    assert len(figures) == 4 and all(not seal_issues(ROOT, f["files"] + f["sources"]) for f in figures)
    assert (ROOT / "paper3/main.pdf").is_file()
    assert not read_json(ROOT / cfg["reports"] / "TESS_SCOPE_DECISION.json")["broader_TESS_expansion"]
