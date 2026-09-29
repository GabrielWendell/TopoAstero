"""Seal each Stage 8 deliverable group after workflow, notebook, build, and tests."""

from __future__ import annotations

from pathlib import Path

from topoastero.portability import write_csv_lf
from topoastero.provenance import sha256_file

ROOT = Path(__file__).parents[1]
TARGET = ROOT / "reports/stage8/deliverable_manifest.csv"
DELIVERABLES = {
    "D8.1": [
        "configs/stage8_echelle.yaml", "src/topoastero/echelle_topology.py",
        "schemas/cylindrical_pair.schema.json", "results/stage8/diagram_suite.json",
        "reports/stage8/figures/paired_echelle.svg",
    ],
    "D8.2": [
        "schemas/echelle_score.schema.json", "results/stage8/score_curves.csv",
        "results/stage8/paired_benchmark.csv", "results/stage8/null_maxima.csv",
        "reports/stage8/ALIAS_AND_ABLATION_REPORT.md",
        "reports/stage8/figures/score_curves.svg", "reports/stage8/figures/paired_method_accuracy.svg",
    ],
    "D8.3": [
        "schemas/stage8_interval.schema.json", "results/stage8/intervals.csv",
        "results/stage8/bootstrap_draws.csv", "results/stage8/failure_atlas.csv",
        "reports/stage8/UNCERTAINTY_AND_FAILURE_ATLAS.md",
        "reports/stage8/figures/interval_coverage.svg",
    ],
    "D8.4": [
        "results/stage8/ratio_audit.csv", "reports/stage8/RIDGE_ANGLES_AND_RATIO_AUDIT.md",
        "reports/stage8/figures/published_ratio_formula_audit.svg",
    ],
    "G8": [
        "registries/stage8_simulation_lock.yaml", "registries/stage8_decision_policy.yaml",
        "docs/science/CYLINDRICAL_ECHELLE_MATHEMATICS.md",
        "docs/protocols/STAGE8_ECHELLE_PROTOCOL.md",
        "schemas/stage8_gate.schema.json", "schemas/stage8_run_manifest.schema.json",
        "results/stage8/environment.json", "results/stage8/run_manifest.json",
        "reports/stage8/STAGE8_REPORT.md", "reports/stage8/TRACEABILITY_MATRIX.md",
        "reports/stage8/G8_ACCEPTANCE.json", "notebooks/08_cylindrical_echelle.ipynb",
        "src/topoastero/stage8_validation.py", "workflows/run_stage8_echelle.py",
        "workflows/validate_stage8.py", "workflows/execute_stage8_notebook.py",
        "tests/unit/test_echelle_topology.py",
        "tests/governance/test_stage8_schemas.py", "tests/governance/test_stage8_contract.py",
        "tests/integration/test_stage8_cli.py",
    ],
    "software": [
        "README.md", "CHANGELOG.md", "CITATION.cff", "pyproject.toml", "uv.lock",
        "src/topoastero/__init__.py", "src/topoastero/cli.py",
        "src/topoastero/portability.py", "workflows/repair_portability.py",
        "workflows/build_stage8_manifest.py", ".gitignore", ".github/workflows/ci.yml",
        "registries/experiment_ledger.csv", "registries/decision_log.csv",
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
            rows.append({
                "deliverable": deliverable, "path": relative,
                "size_bytes": path.stat().st_size, "sha256": sha256_file(path),
                "status": "accepted",
            })
    write_csv_lf(TARGET, rows, fieldnames=["deliverable", "path", "size_bytes", "sha256", "status"])


if __name__ == "__main__":
    main()
