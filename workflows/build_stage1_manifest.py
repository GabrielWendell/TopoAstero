"""Build the Stage 1 deliverable checksum index."""

from __future__ import annotations

import csv
from pathlib import Path

from topoastero.provenance import sha256_file

ROOT = Path(__file__).parents[1]
TARGET = ROOT / "reports/stage1/deliverable_manifest.csv"

DELIVERABLES = {
    "D1.1": [
        "evidence/README.md",
        "evidence/literature/literature_matrix.csv",
        "evidence/literature/physics_matrix.csv",
        "evidence/literature/classical_baseline_matrix.csv",
        "evidence/literature/theorem_matrix.csv",
        "evidence/literature/astronomy_tda_gap_map.csv",
        "evidence/literature/hypothesis_baseline_crosswalk.csv",
        "docs/literature/SOLAR_LIKE_PHYSICS_MAP.md",
        "docs/literature/CLASSICAL_PIPELINE_MAP.md",
        "docs/literature/MATHEMATICAL_TDA_MAP.md",
        "docs/literature/ASTRONOMY_TDA_GAP_MAP.md",
    ],
    "D1.2": [
        "docs/literature/RESEARCH_GAP_MEMORANDUM.md",
        "docs/literature/NOVELTY_AUDIT.md",
        "evidence/search/novelty_search_log.csv",
    ],
    "D1.3": [
        "evidence/benchmarks/rudy_identity.yaml",
        "evidence/benchmarks/legacy_population.csv",
        "evidence/benchmarks/benchmark_targets.csv",
        "evidence/benchmarks/rudy_mode_frequencies.csv",
        "evidence/benchmarks/source_provenance.csv",
        "docs/benchmarks/RUDY_BENCHMARK_SPECIFICATION.md",
        "docs/benchmarks/LEGACY_POPULATION_SPECIFICATION.md",
    ],
    "D1.4": [
        "evidence/references/reference_audit.csv",
        "evidence/references/topoastero_stage1.bib",
        "docs/literature/REFERENCE_UPDATE_PROTOCOL.md",
        "schemas/literature_evidence.schema.json",
        "schemas/benchmark_target.schema.json",
        "schemas/reference_audit.schema.json",
        "schemas/novelty_search.schema.json",
    ],
    "G1": [
        "reports/stage1/TRACEABILITY_MATRIX.md",
        "reports/stage1/STAGE1_REPORT.md",
        "reports/stage1/G1_ACCEPTANCE.json",
        "src/topoastero/evidence.py",
        "src/topoastero/stage1_validation.py",
        "workflows/build_stage1_benchmarks.py",
        "workflows/build_stage1_manifest.py",
        "workflows/validate_stage1.py",
        "tests/unit/test_evidence.py",
        "tests/governance/test_stage1_contract.py",
        "tests/integration/test_stage1_cli.py",
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
