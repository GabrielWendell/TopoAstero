"""Stage 8 locked decision and evidence integrity."""

from __future__ import annotations

import json
from pathlib import Path

from topoastero.stage8_validation import REQUIRED_FILES, _record_seals, validate_stage8

ROOT = Path(__file__).parents[2]


def test_stage8_passes_with_all_prior_stage_regressions() -> None:
    assert validate_stage8(ROOT) == []


def test_g8_narrows_claim_when_topology_does_not_beat_graph() -> None:
    gate = json.loads((ROOT / "reports/stage8/G8_ACCEPTANCE.json").read_text())
    assert gate["gate"] == "G8" and gate["status"] == "pass"
    assert gate["decision"] == "geometry_only"
    assert gate["claim"] == "correct_cylindrical_geometry_only"
    assert gate["alias_accuracy_topology"] < gate["alias_accuracy_graph"]
    assert gate["population_spectra_used"] is False
    assert gate["final_holdout_used"] is False
    report = (ROOT / "reports/stage8/STAGE8_REPORT.md").read_text()
    assert "no claim" in report.lower()


def test_stage8_traceability_and_required_artifacts() -> None:
    trace = (ROOT / "reports/stage8/TRACEABILITY_MATRIX.md").read_text()
    for task in range(1, 11):
        assert f"T8.{task}" in trace
    assert all((ROOT / path).is_file() for path in REQUIRED_FILES)


def test_missing_contract_and_path_escape_are_detected(tmp_path: Path) -> None:
    assert any("missing" in error for error in validate_stage8(tmp_path, require_prior_stages=False))
    errors: list[str] = []
    _record_seals(tmp_path, [{"path": "../outside", "sha256": "bogus"}], "test", errors)
    assert any("invalid test path" in error for error in errors)
