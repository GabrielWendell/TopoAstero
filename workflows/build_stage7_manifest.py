"""Build the Stage 7 deliverable checksum index."""

from __future__ import annotations

from pathlib import Path

from topoastero.portability import write_csv_lf
from topoastero.provenance import sha256_file

ROOT = Path(__file__).parents[1]
TARGET = ROOT / "reports/stage7/deliverable_manifest.csv"

DELIVERABLES = {
    "D7.1": [
        "configs/stage7_delay_topology.yaml",
        "registries/stage7_delay_policy.yaml",
        "src/topoastero/delay_topology.py",
        "schemas/delay_embedding.schema.json",
        "results/stage7/delay_parameter_audit.csv",
        "results/stage7/delay_policy_summary.csv",
        "results/stage7/embedding_audit.csv",
        "reports/stage7/figures/delay_policy_comparison.svg",
        "reports/stage7/figures/embedding_and_h1_diagram.svg",
    ],
    "D7.2": [
        "schemas/delay_diagram.schema.json",
        "results/stage7/diagram_suite.json",
        "results/stage7/convergence_audit.csv",
        "results/stage7/coherence_response_surfaces.csv",
        "results/stage7/response_correlations.csv",
        "reports/stage7/COHERENCE_AND_ABLATION_REPORT.md",
        "reports/stage7/figures/coherence_response_surface.svg",
    ],
    "D7.3": [
        "schemas/phase_test.schema.json",
        "results/stage7/phase_tests.csv",
        "results/stage7/surrogate_draw_maxima.csv",
        "results/stage7/classical_controls.csv",
        "results/stage7/predictive_ablation.csv",
        "reports/stage7/PHASE_INFORMATION_TEST.md",
        "reports/stage7/figures/phase_surrogate_tests.svg",
        "reports/stage7/figures/classical_control_ablation.svg",
    ],
    "D7.4": [
        "results/stage7/segmentation_stability.csv",
        "results/stage7/vineyard_tracks.csv",
        "reports/stage7/SEGMENTATION_STABILITY_REPORT.md",
        "reports/stage7/RETAIN_DROP_DECISION.md",
        "reports/stage7/figures/segmentation_stability.svg",
    ],
    "G7": [
        "registries/stage7_simulation_lock.yaml",
        "registries/stage7_decision_policy.yaml",
        "docs/science/DELAY_EMBEDDING_PHASE_TEST.md",
        "docs/protocols/STAGE7_DELAY_TOPOLOGY_PROTOCOL.md",
        "schemas/stage7_decision.schema.json",
        "schemas/stage7_run_manifest.schema.json",
        "results/stage7/environment.json",
        "results/stage7/run_manifest.json",
        "reports/stage7/STAGE7_REPORT.md",
        "reports/stage7/TRACEABILITY_MATRIX.md",
        "reports/stage7/G7_ACCEPTANCE.json",
        "src/topoastero/stage7_validation.py",
        "workflows/run_stage7_delay_topology.py",
        "workflows/validate_stage7.py",
        "notebooks/07_delay_embedding_phase_test.ipynb",
        "tests/unit/test_delay_topology.py",
        "tests/governance/test_stage7_contract.py",
        "tests/governance/test_stage7_schemas.py",
        "tests/integration/test_stage7_cli.py",
    ],
    "software": [
        "README.md",
        "CHANGELOG.md",
        "CITATION.cff",
        "pyproject.toml",
        "uv.lock",
        "dist/topoastero-0.8.0-py3-none-any.whl",
        "dist/topoastero-0.8.0.tar.gz",
        "src/topoastero/__init__.py",
        "src/topoastero/cli.py",
        "registries/experiment_ledger.csv",
        "registries/decision_log.csv",
        "registries/change_log.csv",
        "workflows/build_stage7_manifest.py",
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

