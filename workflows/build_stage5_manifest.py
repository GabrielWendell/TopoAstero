"""Build the Stage 5 deliverable checksum index."""

from __future__ import annotations

from pathlib import Path

from topoastero.portability import write_csv_lf
from topoastero.provenance import sha256_file

ROOT = Path(__file__).parents[1]
TARGET = ROOT / "reports/stage5/deliverable_manifest.csv"

DELIVERABLES = {
    "D5.1": [
        "src/topoastero/tda.py",
        "src/topoastero/representations.py",
        "tests/unit/test_tda.py",
        "tests/unit/test_representations.py",
        "results/stage5/backend_crosscheck.csv",
        "reports/stage5/BACKEND_CROSSCHECK_REPORT.md",
        "reports/stage5/figures/backend_crosschecks.svg",
    ],
    "D5.2": [
        "configs/stage5_tda.yaml",
        "docs/science/TDA_REPRESENTATION_SPECIFICATION.md",
        "docs/protocols/STAGE5_REPRESENTATION_AUDIT_PROTOCOL.md",
        "registries/stage5_representation_parameters.yaml",
        "registries/stage5_feature_registry.csv",
        "schemas/representation_spec.schema.json",
        "schemas/topological_feature.schema.json",
    ],
    "D5.3": [
        "docs/science/LOCALIZATION_AND_INTERPRETATION.md",
        "schemas/localization.schema.json",
        "results/stage5/localization_catalog.json",
        "reports/stage5/figures/representation_atlas.svg",
        "reports/stage5/figures/localization_atlas.svg",
    ],
    "D5.4": [
        "results/stage5/representation_features.csv",
        "results/stage5/null_calibration.csv",
        "results/stage5/nuisance_sensitivity.csv",
        "results/stage5/redundancy_matrix.csv",
        "results/stage5/redundancy_pairs.csv",
        "results/stage5/ablation_results.csv",
        "results/stage5/selection_scores.csv",
        "registries/stage5_selection.yaml",
        "schemas/selection_record.schema.json",
        "reports/stage5/SENSITIVITY_REPORT.md",
        "reports/stage5/REDUNDANCY_AND_ABLATION_REPORT.md",
        "reports/stage5/REPRESENTATION_SELECTION_MEMO.md",
        "reports/stage5/figures/nuisance_sensitivity.svg",
        "reports/stage5/figures/redundancy_matrix.svg",
        "reports/stage5/figures/ablation_utility.svg",
        "reports/stage5/figures/selection_summary.svg",
    ],
    "G5": [
        "results/stage5/run_manifest.json",
        "results/stage5/environment.json",
        "reports/stage5/STAGE5_REPORT.md",
        "reports/stage5/TRACEABILITY_MATRIX.md",
        "reports/stage5/G5_ACCEPTANCE.json",
        "schemas/stage5_run_manifest.schema.json",
        "src/topoastero/stage5_validation.py",
        "workflows/run_stage5_tda_audit.py",
        "workflows/validate_stage5.py",
        "notebooks/05_tda_representation_audit.ipynb",
        "tests/governance/test_stage5_contract.py",
        "tests/governance/test_stage5_schemas.py",
        "tests/integration/test_stage5_cli.py",
    ],
    "software": [
        "README.md",
        "CHANGELOG.md",
        "CITATION.cff",
        "pyproject.toml",
        "uv.lock",
        "dist/topoastero-0.6.0-py3-none-any.whl",
        "dist/topoastero-0.6.0.tar.gz",
        "src/topoastero/__init__.py",
        "src/topoastero/cli.py",
        "registries/experiment_ledger.csv",
        "registries/decision_log.csv",
        "registries/change_log.csv",
        "workflows/build_stage5_manifest.py",
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
