"""Build the Stage 4 deliverable checksum index."""

from __future__ import annotations

from pathlib import Path

from topoastero.portability import write_csv_lf
from topoastero.provenance import sha256_file

ROOT = Path(__file__).parents[1]
TARGET = ROOT / "reports/stage4/deliverable_manifest.csv"

DELIVERABLES = {
    "D4.1": [
        "docs/derivations/STAGE4_ANALYTIC_CASES.md",
        "results/stage4/analytic_cases.csv",
        "reports/stage4/figures/analytic_cases.svg",
        "tests/unit/test_simulation_lab.py",
    ],
    "D4.2": [
        "src/topoastero/simulation_lab.py",
        "docs/science/STOCHASTIC_OSCILLATOR_MODEL.md",
        "results/stage4/simulator_validation.csv",
        "results/stage4/mode_recovery.csv",
        "results/stage4/sample_spectrum.csv",
        "results/stage4/sample_light_curve.csv",
        "reports/stage4/SIMULATOR_VALIDATION.md",
        "reports/stage4/figures/simulator_recovery.svg",
        "reports/stage4/figures/mission_observation_effects.svg",
    ],
    "D4.3": [
        "configs/stage4_simulation.yaml",
        "registries/stage4_factorial_design.csv",
        "data/derived/stage4/mission_window_templates.csv",
        "results/stage4/factorial_pilot.csv",
        "results/stage4/null_calibration.csv",
        "results/stage4/multiplicity_thresholds.csv",
        "results/stage4/run_manifest.json",
        "reports/stage4/NULL_CALIBRATION_REPORT.md",
        "reports/stage4/figures/null_calibration.svg",
        "workflows/build_stage4_window_templates.py",
        "workflows/run_stage4_simulation_lab.py",
    ],
    "D4.4": [
        "results/stage4/uncertainty_coverage.csv",
        "results/stage4/compute_profile.csv",
        "results/stage4/precision_budget.json",
        "reports/stage4/UNCERTAINTY_AND_COMPUTE_REPORT.md",
        "reports/stage4/figures/coverage_map.svg",
        "reports/stage4/figures/compute_profile.svg",
        "notebooks/04_simulation_lab.ipynb",
    ],
    "G4": [
        "registries/stage4_confirmation_protocol.yaml",
        "docs/protocols/STAGE4_SIMULATION_PROTOCOL.md",
        "docs/protocols/STAGE4_CONFIRMATION_PROTOCOL.md",
        "reports/stage4/STAGE4_REPORT.md",
        "reports/stage4/TRACEABILITY_MATRIX.md",
        "reports/stage4/G4_ACCEPTANCE.json",
        "schemas/simulation_design.schema.json",
        "schemas/null_calibration.schema.json",
        "schemas/coverage_result.schema.json",
        "schemas/compute_profile.schema.json",
        "schemas/stage4_run_manifest.schema.json",
        "src/topoastero/stage4_validation.py",
        "workflows/validate_stage4.py",
        "tests/governance/test_stage4_contract.py",
        "tests/governance/test_stage4_schemas.py",
        "tests/integration/test_stage4_cli.py",
    ],
    "software": [
        "README.md",
        "CHANGELOG.md",
        "CITATION.cff",
        "pyproject.toml",
        "uv.lock",
        ".github/workflows/ci.yml",
        ".gitignore",
        "src/topoastero/__init__.py",
        "src/topoastero/cli.py",
        "src/topoastero/portability.py",
        "workflows/repair_portability.py",
        "tests/unit/test_portability.py",
        "workflows/README.md",
        "configs/README.md",
        "data/derived/README.md",
        "results/README.md",
        "registries/experiment_ledger.csv",
        "registries/decision_log.csv",
        "registries/change_log.csv",
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
    write_csv_lf(
        TARGET,
        rows,
        fieldnames=["deliverable", "path", "size_bytes", "sha256", "status"],
    )


if __name__ == "__main__":
    main()
