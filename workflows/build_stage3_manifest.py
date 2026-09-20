"""Build the Stage 3 deliverable checksum index."""

from __future__ import annotations

import csv
from pathlib import Path

from topoastero.provenance import sha256_file

ROOT = Path(__file__).parents[1]
TARGET = ROOT / "reports/stage3/deliverable_manifest.csv"

DELIVERABLES = {
    "D3.1": [
        "configs/stage3_classical.yaml",
        "workflows/acquire_stage3_inputs.py",
        "workflows/run_stage3_classical.py",
        "notebooks/03_rudy_classical_baseline.ipynb",
        "results/stage3/run_manifest.json",
    ],
    "D3.2": [
        "results/stage3/rudy_baseline.csv",
        "results/stage3/pipeline_comparison.csv",
        "results/stage3/uncertainty_budget.csv",
        "reports/stage3/PIPELINE_COMPARISON.md",
        "schemas/classical_result.schema.json",
        "schemas/stage3_run_manifest.schema.json",
    ],
    "D3.3": [
        "results/stage3/background_models.csv",
        "results/stage3/window_atlas.csv",
        "results/stage3/preprocessing_sensitivity.csv",
        "registries/preprocessing_branches.csv",
        "reports/stage3/SENSITIVITY_REPORT.md",
        "reports/stage3/figures/background_comparison.svg",
        "reports/stage3/figures/window_atlas.svg",
        "schemas/preprocessing_branch.schema.json",
    ],
    "D3.4": [
        "results/stage3/reduced_spectrum.csv",
        "results/stage3/echelle_trials.csv",
        "results/stage3/mode_audit.csv",
        "reports/stage3/figures/rudy_power_spectrum.svg",
        "reports/stage3/figures/echelle_trials.svg",
        "reports/stage3/figures/mode_overlay_audit.svg",
    ],
    "D3.5": [
        "results/stage3/tess_sector_feasibility.csv",
        "reports/stage3/TESS_FEASIBILITY_NOTE.md",
        "reports/stage3/figures/tess_sector_feasibility.svg",
        "schemas/tess_feasibility.schema.json",
    ],
    "G3": [
        "docs/protocols/STAGE3_CLASSICAL_BASELINE_PROTOCOL.md",
        "docs/science/CLASSICAL_OBSERVATION_MODEL.md",
        "reports/stage3/STAGE3_REPORT.md",
        "reports/stage3/TRACEABILITY_MATRIX.md",
        "reports/stage3/G3_ACCEPTANCE.json",
        "src/topoastero/classical.py",
        "src/topoastero/stage3_validation.py",
        "workflows/validate_stage3.py",
        "tests/unit/test_classical.py",
        "tests/governance/test_stage3_contract.py",
        "tests/governance/test_stage3_schemas.py",
        "tests/integration/test_stage3_cli.py",
    ],
    "software": [
        "README.md",
        "CHANGELOG.md",
        "CITATION.cff",
        "pyproject.toml",
        "uv.lock",
        ".github/workflows/ci.yml",
        "src/topoastero/__init__.py",
        "src/topoastero/cli.py",
        "workflows/README.md",
        "configs/README.md",
        "registries/experiment_ledger.csv",
        "registries/decision_log.csv",
    ],
}


def main() -> None:
    rows: list[dict[str, str | int]] = []
    for deliverable, paths in DELIVERABLES.items():
        for relative in paths:
            path = ROOT / relative
            if not path.is_file():
                raise FileNotFoundError(path)
            rows.append(
                {
                    "deliverable": deliverable,
                    "path": relative,
                    "size_bytes": path.stat().st_size,
                    "sha256": sha256_file(path),
                    "status": "accepted",
                }
            )
    TARGET.parent.mkdir(parents=True, exist_ok=True)
    with TARGET.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle, fieldnames=["deliverable", "path", "size_bytes", "sha256", "status"]
        )
        writer.writeheader()
        writer.writerows(rows)


if __name__ == "__main__":
    main()
