"""Build the Stage 6 deliverable checksum index."""

from __future__ import annotations

from pathlib import Path

from topoastero.portability import write_csv_lf
from topoastero.provenance import sha256_file

ROOT = Path(__file__).parents[1]
TARGET = ROOT / "reports/stage6/deliverable_manifest.csv"

DELIVERABLES = {
    "D6.1": [
        "configs/stage6_psd_topology.yaml",
        "registries/stage6_normalization_contract.yaml",
        "docs/science/PSD_PERSISTENCE_METHOD.md",
        "src/topoastero/spectral_topology.py",
        "schemas/psd_persistence_pair.schema.json",
        "results/stage6/normalization_audit.csv",
        "results/stage6/peak_diagram.json",
        "reports/stage6/figures/normalized_spectrum_and_diagram.svg",
    ],
    "D6.2": [
        "schemas/numax_estimate.schema.json",
        "schemas/comb_candidate.schema.json",
        "results/stage6/numax_benchmark.csv",
        "results/stage6/numax_summary.csv",
        "results/stage6/comb_candidates.csv",
        "results/stage6/comb_benchmark.csv",
        "results/stage6/pysyd_adapter_audit.json",
        "reports/stage6/figures/numax_comparison.svg",
        "reports/stage6/figures/comb_alias_atlas.svg",
    ],
    "D6.3": [
        "registries/stage6_quality_flags.yaml",
        "schemas/spectral_quality.schema.json",
        "results/stage6/null_calibration.csv",
        "results/stage6/null_draw_maxima.csv",
        "results/stage6/quality_flags.csv",
        "reports/stage6/NULL_CALIBRATION_AND_QC_REPORT.md",
        "reports/stage6/figures/null_calibration.svg",
        "reports/stage6/figures/quality_flags.svg",
    ],
    "D6.4": [
        "results/stage6/equivalence_audit.csv",
        "results/stage6/robustness_atlas.csv",
        "reports/stage6/EQUIVALENCE_AND_ABLATION_REPORT.md",
        "reports/stage6/ROBUSTNESS_ATLAS.md",
        "reports/stage6/figures/prominence_equivalence.svg",
        "reports/stage6/figures/robustness_atlas.svg",
    ],
    "G6": [
        "registries/stage6_simulation_lock.yaml",
        "docs/protocols/STAGE6_PSD_TOPOLOGY_PROTOCOL.md",
        "schemas/stage6_run_manifest.schema.json",
        "results/stage6/environment.json",
        "results/stage6/run_manifest.json",
        "reports/stage6/STAGE6_REPORT.md",
        "reports/stage6/TRACEABILITY_MATRIX.md",
        "reports/stage6/G6_ACCEPTANCE.json",
        "src/topoastero/stage6_validation.py",
        "workflows/run_stage6_psd_topology.py",
        "workflows/validate_stage6.py",
        "notebooks/06_psd_persistence.ipynb",
        "tests/unit/test_spectral_topology.py",
        "tests/governance/test_stage6_contract.py",
        "tests/governance/test_stage6_schemas.py",
        "tests/integration/test_stage6_cli.py",
    ],
    "software": [
        "README.md",
        "CHANGELOG.md",
        "CITATION.cff",
        "pyproject.toml",
        "uv.lock",
        "src/topoastero/__init__.py",
        "src/topoastero/cli.py",
        "registries/experiment_ledger.csv",
        "registries/decision_log.csv",
        "registries/change_log.csv",
        "workflows/build_stage6_manifest.py",
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
