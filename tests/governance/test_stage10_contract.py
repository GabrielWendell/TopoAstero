"""Scope, branch completeness, immutable snapshot and pending-review regressions."""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

import topoastero.stage10_validation as validation
from topoastero.config import load_yaml

ROOT = Path(__file__).parents[2]


@pytest.mark.governance
def test_stage10_frozen_contract_and_prior_gates() -> None:
    assert validation.validate_stage10(ROOT) == []
    gate = json.loads((ROOT / "reports/stage10/G10_ACCEPTANCE.json").read_text())
    assert gate["implementation_status"] == "pass"
    assert gate["status"] == "review_pending"
    assert gate["independent_human_review"] == "pending"


def test_missing_stage10_is_a_clear_failure(tmp_path: Path) -> None:
    issues = validation.validate_stage10(tmp_path, require_prior_stages=False)
    assert issues and all(issue.startswith("missing Stage 10") for issue in issues)


@pytest.mark.parametrize("file,key,value,expected", [
    ("summary.json", "population_spectra_used", True, "scope leaks"),
    ("summary.json", "delay_status", "run_Rudy_delay_PH", "prior negative"),
    ("summary.json", "maximum_prominence_equivalence_error", 0.1, "prominence identity"),
    ("benchmark_capsule.json", "product_count", 20, "21 frozen"),
    ("cylinder.json", "inferred_r02", 0.08, "unsupported blind"),
    ("G10_ACCEPTANCE.json", "status", "pass", "falsely reports"),
    ("clean_reproduction.json", "independent_human_reviewer", "a machine", "masquerades"),
    ("claim_audit.json", "unsupported_claims", ["P1-C04"], "unsupported or stale"),
])
def test_science_gate_rejects_overclaiming(monkeypatch: pytest.MonkeyPatch, file: str, key: str, value: object, expected: str) -> None:
    original = validation._json

    def altered(path: Path) -> dict:
        record = copy.deepcopy(original(path))
        if path.name == file:
            record[key] = value
        return record

    monkeypatch.setattr(validation, "_json", altered)
    assert any(expected in issue for issue in validation.validate_stage10(ROOT, require_prior_stages=False))


def test_normalization_branches_cannot_be_silently_dropped(monkeypatch: pytest.MonkeyPatch) -> None:
    original = validation._csv

    def altered(path: Path) -> list[dict[str, str]]:
        data = original(path)
        return data[1:] if path.name == "robustness.csv" else data

    monkeypatch.setattr(validation, "_csv", altered)
    assert any("branches omitted" in issue for issue in validation.validate_stage10(ROOT, require_prior_stages=False))


def test_actual_review_record_remains_empty() -> None:
    review = load_yaml(ROOT / "registries/stage10_independent_review.yaml")
    assert validation.independent_review_accepted(ROOT, review) == (False, [])
    assert review["reviewer_name"] is None and review["document_sha256"] is None
