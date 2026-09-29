"""Build G9 review hold, provenance seals, and deliverable index after the audit."""

from __future__ import annotations

import json
from pathlib import Path

from topoastero.config import configuration_hash, load_yaml
from topoastero.portability import write_csv_lf, write_json_lf, write_text_lf
from topoastero.provenance import sha256_file

ROOT = Path(__file__).parents[1]
INPUTS = (
    "configs/stage9_mathematics.yaml", "registries/stage9_proof_review.yaml",
    "reports/stage8/G8_ACCEPTANCE.json",
)
GROUPS = {
    "D9.1": (
        "docs/science/STAGE9_THEOREMS_AND_PROOFS.md", "docs/protocols/STAGE9_MATHEMATICAL_AUDIT.md",
        "src/topoastero/mathematical_relations.py", "schemas/stage9_numerical_audit.schema.json",
    ),
    "D9.2": (
        "results/stage9/numerical_audit.json", "results/stage9/environment.json",
        "tests/unit/test_mathematical_relations.py", "workflows/run_stage9_mathematics.py",
        "notebooks/09_mathematical_relations.ipynb", "workflows/execute_stage9_notebook.py",
        "reports/stage9/figures/ridge_jump_bounds.svg", "reports/stage9/figures/gamma_calibration.svg",
    ),
    "D9.3": (
        "results/stage9/counterexamples.json", "reports/stage9/COUNTEREXAMPLE_CATALOG.md",
        "schemas/stage9_counterexamples.schema.json",
    ),
    "D9.4": ("reports/stage9/UNCERTAINTY_PROPAGATION.md",),
    "G9": (
        "registries/stage9_proof_review.yaml", "reports/stage9/PROOF_REVIEW_PACKET.md",
        "reports/stage9/G9_ACCEPTANCE.json", "reports/stage9/STAGE9_REPORT.md",
        "reports/stage9/TRACEABILITY_MATRIX.md", "schemas/stage9_gate.schema.json",
        "schemas/stage9_run_manifest.schema.json", "results/stage9/run_manifest.json",
        "src/topoastero/stage9_validation.py", "workflows/validate_stage9.py",
        "tests/governance/test_stage9_contract.py", "tests/governance/test_stage9_schemas.py",
        "tests/integration/test_stage9_cli.py",
    ),
    "software": (
        "README.md", "CHANGELOG.md", "CITATION.cff", "pyproject.toml", "uv.lock",
        "src/topoastero/__init__.py", "src/topoastero/cli.py",
        ".github/workflows/ci.yml", "workflows/README.md",
        "workflows/build_stage9_manifest.py", "workflows/repair_portability.py",
        "registries/decision_log.csv",
        "registries/change_log.csv", "registries/experiment_ledger.csv",
    ),
}


def _seal(relative: str) -> dict[str, str | int]:
    path = ROOT / relative
    if not path.is_file():
        raise FileNotFoundError(path)
    return {"path": relative, "size_bytes": path.stat().st_size, "sha256": sha256_file(path)}


def _review_accepted(review: dict[str, object]) -> bool:
    if review.get("status") == "pending_external_review":
        if any(review.get(key) is not None for key in (
            "reviewer_name", "reviewer_affiliation", "reviewer_independent_of_authors",
            "review_date", "document_sha256", "decision",
        )) or review.get("reviewed_claim_ids") != []:
            raise ValueError("pending review record must not imply an attestation")
        return False
    if review.get("status") != "accepted":
        raise ValueError("unknown review status")
    if not (isinstance(review.get("reviewer_name"), str) and review["reviewer_name"]
            and isinstance(review.get("reviewer_affiliation"), str) and review["reviewer_affiliation"]
            and review.get("reviewer_independent_of_authors") is True
            and isinstance(review.get("review_date"), str) and review["review_date"]
            and review.get("decision") == "accepted"
            and "S9-T1" in review.get("reviewed_claim_ids", [])
            and review.get("document_sha256") == sha256_file(ROOT / str(review["reviewed_document"]))):
        raise ValueError("accepted review lacks an independent signed, exact-document attestation")
    return True


def main() -> None:
    config = load_yaml(ROOT / "configs/stage9_mathematics.yaml")
    review = load_yaml(ROOT / "registries/stage9_proof_review.yaml")
    audit = json.loads((ROOT / "results/stage9/numerical_audit.json").read_text())
    if audit["run_id"] != config["run_id"] or audit["stage8_decision"] != "geometry_only":
        raise ValueError("numerical audit disagrees with frozen protocol")
    accepted = _review_accepted(review)
    status = "pass" if accepted else "review_pending"
    gate = {
        "gate": "G9", "run_id": config["run_id"], "status": status,
        "implementation_status": "pass", "new_claim": "S9-T1",
        "review_id": review["review_id"], "review_status": review["status"],
        "review_document_sha256": review["document_sha256"],
        "prior_stage8_decision": "geometry_only", "population_spectra_used": False,
        "final_holdout_used": False,
        "checks": [
            {"check": "exact_identities_and_property_regressions", "status": "pass"},
            {"check": "fixed_mask_stability_and_conditional_target_bound", "status": "pass"},
            {"check": "probabilistic_and_stellar_systematics_calibration", "status": "pass"},
            {"check": "counterexamples_and_claim_classification", "status": "pass"},
            {"check": "independent_human_proof_review", "status": "pass" if accepted else "pending"},
        ],
    }
    write_json_lf(ROOT / "reports/stage9/G9_ACCEPTANCE.json", gate)
    report = f"""# Stage 9 mathematical audit — TA-S09-MATH-R001

Implementation integrity: **PASS**. Scientific gate G9: **{status}**.
The new S9-T1 conditional finite-order target-ridge proposition is documented
and tested, but independent human proof review is {'recorded' if accepted else 'outstanding'}.
The inherited Stage 8 verdict is **geometry_only**; this stage has used no
population spectra or final holdout and makes no new estimator-utility claim.

The seeded audit includes {audit['path_cases']} path identity cases,
{audit['cylinder_cases']} masked-cylinder stability cases and
{audit['ridge_cases']} ridge inequality cases. Maximum numerical inequality
violation is {max(audit[key] for key in audit if key.startswith('max_')):.3g}.
For {audit['gamma_replicates']} independent Gamma({audit['gamma_shape']},
scale=1/{audit['gamma_shape']}) vectors of {audit['gamma_bins']} raw bins,
the alpha={audit['gamma_alpha']} union-bound radius is
{audit['gamma_radius']:.6f}; observed exceedances are
{audit['gamma_exceedances']} ({audit['gamma_exceedance_rate']:.4f}),
with Wilson 95% interval [{audit['gamma_wilson95'][0]:.4f},
{audit['gamma_wilson95'][1]:.4f}]. This is model-family calibration, not
validation for smoothed Stage 8 PSDs.

See D9.1 for proofs and claim classification, D9.2 for numerical evidence
and figures, D9.3 for nine counterexamples, D9.4 for separate seismic and
astrophysical uncertainty allowances, and the independent review packet.
"""
    write_text_lf(ROOT / "reports/stage9/STAGE9_REPORT.md", report)
    outputs = [relative for group in GROUPS.values() for relative in group
               if relative not in INPUTS and relative != "results/stage9/run_manifest.json"]
    manifest = {
        "run_id": config["run_id"], "config_sha256": configuration_hash(ROOT / INPUTS[0]),
        "software_version": config["software_version"], "style_id": "TA-PLOT-1.0",
        "status": "implementation_complete", "gate_status": status,
        "population_spectra_used": False, "final_holdout_used": False,
        "inputs": [_seal(relative) for relative in INPUTS],
        "outputs": [_seal(relative) for relative in dict.fromkeys(outputs)],
    }
    write_json_lf(ROOT / "results/stage9/run_manifest.json", manifest)
    rows = []
    for group, paths in GROUPS.items():
        for relative in paths:
            rows.append({"deliverable": group, **_seal(relative),
                         "status": status if group == "G9" else "implemented"})
    write_csv_lf(ROOT / "reports/stage9/deliverable_manifest.csv", rows,
                 fieldnames=["deliverable", "path", "size_bytes", "sha256", "status"])
    print(f"Stage 9 manifest sealed; G9 {status}")


if __name__ == "__main__":
    main()
