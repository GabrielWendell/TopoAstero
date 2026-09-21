from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

from topoastero.config import load_yaml
from topoastero.validation import (
    REQUIRED_DATASETS,
    REQUIRED_HYPOTHESES,
    REQUIRED_OBJECTIVES,
    REQUIRED_QUESTIONS,
    REQUIRED_TERMS,
)

ROOT = Path(__file__).parents[2]


@pytest.mark.governance
def test_scientific_registry_is_complete() -> None:
    hypotheses = load_yaml(ROOT / "registries/hypotheses.yaml")["hypotheses"]
    assert {entry["id"] for entry in hypotheses} == REQUIRED_HYPOTHESES
    for entry in hypotheses:
        assert entry["null_hypothesis"]
        assert entry["estimand"]["definition"]
        assert entry["baseline"]["primary"]
        assert entry["minimum_publishable_conclusion"]
        assert entry["falsification_rule"]

    crosswalk = load_yaml(ROOT / "registries/objective_crosswalk.yaml")
    assert {entry["id"] for entry in crosswalk["objectives"]} == REQUIRED_OBJECTIVES
    assert {entry["id"] for entry in crosswalk["research_questions"]} == REQUIRED_QUESTIONS


@pytest.mark.governance
def test_terms_and_datasets_cover_stage_gate() -> None:
    terms = load_yaml(ROOT / "registries/terminology.yaml")["terms"]
    assert {entry["id"] for entry in terms} >= REQUIRED_TERMS
    datasets = load_yaml(ROOT / "data/manifests/planned_datasets.yaml")["datasets"]
    assert {entry["id"] for entry in datasets} == REQUIRED_DATASETS
    assert all(entry["resolution_stage"] for entry in datasets)
    assert all(entry["license_or_terms"] for entry in datasets)


@pytest.mark.governance
def test_holdout_is_frozen_and_unopened() -> None:
    split = load_yaml(ROOT / "registries/split_policy.yaml")
    assert split["actual_assignments"] == "registries/population_partitions.csv"
    assert split["assignment_status"] == "frozen_T2.8"
    assert split["protection"]["one_time_access"] is True
    with (ROOT / "registries/holdout_access_log.csv").open(
        "r", encoding="utf-8", newline=""
    ) as handle:
        assert list(csv.DictReader(handle)) == []


@pytest.mark.governance
def test_risks_and_decisions_have_owners_and_dates() -> None:
    risks = load_yaml(ROOT / "registries/risk_register.yaml")["risks"]
    assert len(risks) >= 10
    assert {entry["impact"] for entry in risks} <= {"L", "M", "H"}
    assert all(entry["owner_role"] and entry["review_date"] for entry in risks)
    decisions = load_yaml(ROOT / "registries/pilot_decisions.yaml")["decisions"]
    assert all(entry["status"] == "scheduled" for entry in decisions)
    assert all(entry["decision_stage"] and entry["evidence_required"] for entry in decisions)


@pytest.mark.governance
def test_json_schemas_are_well_formed() -> None:
    for path in sorted((ROOT / "schemas").glob("*.json")):
        schema = json.loads(path.read_text(encoding="utf-8"))
        assert schema["$schema"].endswith("2020-12/schema")
        assert schema["title"]
