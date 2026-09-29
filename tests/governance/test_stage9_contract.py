"""Reject stale evidence and prevent machine tests from posing as proof review."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from topoastero.stage9_validation import SCHEMAS, validate_stage9

ROOT = Path(__file__).parents[2]


def _projection(destination: Path) -> None:
    manifest = json.loads((ROOT / "results/stage9/run_manifest.json").read_text())
    with (ROOT / "reports/stage9/deliverable_manifest.csv").open() as handle:
        import csv
        rows = list(csv.DictReader(handle))
    paths = {"reports/stage9/deliverable_manifest.csv", "results/stage9/run_manifest.json"}
    paths.update(f"schemas/{name}" for name in SCHEMAS)
    paths.update(item["path"] for kind in ("inputs", "outputs") for item in manifest[kind])
    paths.update(item["path"] for item in rows)
    for relative in paths:
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / relative, target)


def test_implementation_pass_science_gate_remains_pending() -> None:
    assert validate_stage9(ROOT) == []
    gate = json.loads((ROOT / "reports/stage9/G9_ACCEPTANCE.json").read_text())
    assert gate["implementation_status"] == "pass"
    assert gate["status"] == "review_pending"
    assert gate["checks"][-1] == {"check": "independent_human_proof_review", "status": "pending"}


def test_modified_proof_or_fake_gate_is_rejected(tmp_path: Path) -> None:
    _projection(tmp_path)
    assert validate_stage9(tmp_path, require_prior_stages=False) == []
    chapter = tmp_path / "docs/science/STAGE9_THEOREMS_AND_PROOFS.md"
    chapter.write_text(chapter.read_text() + "\nUnreviewed change.\n")
    assert any("stale" in issue for issue in validate_stage9(tmp_path, require_prior_stages=False))
    shutil.copyfile(ROOT / "docs/science/STAGE9_THEOREMS_AND_PROOFS.md", chapter)
    gate_path = tmp_path / "reports/stage9/G9_ACCEPTANCE.json"
    gate = json.loads(gate_path.read_text())
    gate["status"] = "pass"
    gate_path.write_text(json.dumps(gate))
    assert any("review" in issue for issue in validate_stage9(tmp_path, require_prior_stages=False))


@pytest.mark.parametrize(("relative", "key", "value", "expected"), [
    ("configs/stage9_mathematics.yaml", "text:coefficients: F2", "coefficients: F3", "geometry drifted"),
    ("configs/stage9_mathematics.yaml", "text:geometry_only", "retain", "boundary drifted"),
    ("registries/stage9_proof_review.yaml", "text:pending_external_review", "rejected", "unknown proof review"),
    ("registries/stage9_proof_review.yaml", "text:reviewer_name: null", "reviewer_name: not_signed", "unsigned/fabricated"),
    ("registries/stage9_proof_review.yaml", "text:status: pending_external_review", "status: accepted", "valid ISO date"),
    ("results/stage9/numerical_audit.json", "run_id", "other", "detached"),
    ("results/stage9/numerical_audit.json", "claim_ids", [], "claim registry"),
    ("results/stage9/numerical_audit.json", "max_ridge_inequality_violation", .3, "inequality failed"),
    ("results/stage9/numerical_audit.json", "gamma_shape", 7., "calibration model"),
    ("results/stage9/numerical_audit.json", "gamma_tail_bound", .9, "no longer certifies"),
    ("results/stage9/numerical_audit.json", "gamma_exceedance_rate", .9, "exceedance rate"),
    ("results/stage9/numerical_audit.json", "final_holdout_used", True, "overstates"),
    ("results/stage9/counterexamples.json", "cases", [], "nine distinct"),
    ("results/stage9/counterexamples.json", "cases.0.family", "", "assumptions are missing"),
    ("results/stage9/counterexamples.json", "cases.0.values", [1, 2, 3], "fixture drifted"),
    ("reports/stage9/G9_ACCEPTANCE.json", "status", "pass", "review record"),
    ("reports/stage9/G9_ACCEPTANCE.json", "checks", [], "check list"),
    ("results/stage9/run_manifest.json", "config_sha256", "0" * 64, "identity/config"),
    ("results/stage9/run_manifest.json", "inputs", [], "input provenance"),
    ("results/stage9/run_manifest.json", "outputs", [], "not byte sealed"),
    ("results/stage9/environment.json", "plot_style", "none", "environment/style"),
    ("notebooks/09_mathematical_relations.ipynb", "cells", [], "notebook is unexecuted"),
    ("schemas/stage9_gate.schema.json", "additionalProperties", True, "schema is not closed"),
    ("reports/stage9/figures/ridge_jump_bounds.svg", "text:TA-PLOT-1.0", "unregistered", "lacks source/style"),
    ("docs/science/STAGE9_THEOREMS_AND_PROOFS.md", "text:S9-T1", "UNREVIEWED", "formal claim chapter"),
    ("reports/stage9/deliverable_manifest.csv", "text:D9.4", "D9.X", "deliverable mapping"),
])
def test_stage9_rejects_science_and_provenance_tampering(
    tmp_path: Path, relative: str, key: str, value: object, expected: str
) -> None:
    _projection(tmp_path)
    target = tmp_path / relative
    if key.startswith("text:"):
        original = key.removeprefix("text:")
        assert original in target.read_text()
        target.write_text(target.read_text().replace(original, str(value)))
    else:
        payload = json.loads(target.read_text())
        parts = key.split(".")
        node = payload
        for part in parts[:-1]:
            node = node[int(part)] if part.isdigit() else node[part]
        node[parts[-1]] = value
        target.write_text(json.dumps(payload))
    assert any(expected in issue for issue in validate_stage9(tmp_path, require_prior_stages=False))
