"""Build the compact Stage 0 deliverable checksum index."""

from __future__ import annotations

import csv
from pathlib import Path

from topoastero.provenance import sha256_file

ROOT = Path(__file__).parents[1]
TARGET = ROOT / "reports/stage0/deliverable_manifest.csv"

DELIVERABLES = {
    "D0.1": [
        "docs/governance/PROJECT_CHARTER.md",
        "docs/governance/GOVERNANCE.md",
        "registries/risk_register.yaml",
    ],
    "D0.2": [
        "docs/reproducibility/REPRODUCIBILITY_SPECIFICATION.md",
        "docs/reproducibility/DATA_MANAGEMENT_PLAN.md",
        "uv.lock",
        "schemas/data_manifest.schema.json",
    ],
    "D0.3": [
        "docs/protocols/PREREGISTERED_ANALYSIS_PROTOCOL.md",
        "registries/hypotheses.yaml",
        "registries/objective_crosswalk.yaml",
        "registries/split_policy.yaml",
        "registries/pilot_decisions.yaml",
    ],
    "D0.4": [
        "pyproject.toml",
        ".github/workflows/ci.yml",
        "configs/smoke.yaml",
        "results/smoke/summary.json",
        "results/smoke/run_manifest.json",
    ],
    "G0": [
        "reports/stage0/TRACEABILITY_MATRIX.md",
        "reports/stage0/STAGE0_REPORT.md",
        "reports/stage0/G0_ACCEPTANCE.json",
        "reports/stage0/resource_audit.json",
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
