"""Build the Stage 2 deliverable checksum index."""

from __future__ import annotations

from pathlib import Path

from topoastero.portability import write_csv_lf
from topoastero.provenance import sha256_file

ROOT = Path(__file__).parents[1]
TARGET = ROOT / "reports/stage2/deliverable_manifest.csv"

DELIVERABLES = {
    "D2.1": [
        "configs/stage2_data.yaml",
        "data/manifests/stage2/rudy_aliases.yaml",
        "data/manifests/stage2/rudy_kepler_products.csv",
        "data/manifests/stage2/rudy_tess_products.csv",
        "data/manifests/stage2/mast_query_snapshot.json",
        "data/manifests/stage2/legacy_kepler_product_index.csv",
        "data/manifests/stage2/legacy_kepler_star_inventory.csv",
        "docs/data/DATA_ACQUISITION_AND_PROVENANCE.md",
        "src/topoastero/acquisition.py",
        "workflows/acquire_stage2_products.py",
        "workflows/query_stage2_mast.py",
        "workflows/query_legacy_kepler_inventory.py",
    ],
    "D2.2": [
        "schemas/derived_provenance.schema.json",
        "schemas/identifier_record.schema.json",
        "schemas/mission_product_manifest.schema.json",
        "schemas/light_curve.schema.json",
        "schemas/spectrum.schema.json",
        "schemas/mode_frequency.schema.json",
        "schemas/stellar_reference.schema.json",
        "data/reference/mode_frequencies.csv",
        "data/reference/frequency_ratios.csv",
        "data/reference/stellar_references.csv",
        "data/manifests/stage2/reference_manifest.csv",
        "data/manifests/stage2/reference_sources.csv",
        "data/canonical/examples/light_curve.jsonl",
        "data/canonical/examples/spectrum.jsonl",
        "data/canonical/examples/mode_frequency.jsonl",
        "data/canonical/examples/stellar_reference.jsonl",
        "docs/data/CANONICAL_DATA_MODEL.md",
        "src/topoastero/data_model.py",
        "workflows/build_stage2_examples.py",
        "workflows/build_stage2_reference_data.py",
    ],
    "D2.3": [
        "docs/protocols/STAGE2_QC_AND_EXCLUSION_PROTOCOL.md",
        "registries/exclusion_ledger.csv",
        "reports/stage2/qc_report.json",
        "reports/stage2/QC_REPORT.md",
        "workflows/build_stage2_qc.py",
    ],
    "D2.4": [
        "schemas/population_split.schema.json",
        "registries/split_policy.yaml",
        "registries/population_partitions.csv",
        "registries/split_attestation.json",
        "registries/holdout_access_log.csv",
        "reports/stage2/partition_balance.json",
        "docs/protocols/SPLIT_AND_HOLDOUT_POLICY.md",
        "workflows/build_stage2_partitions.py",
    ],
    "G2": [
        "reports/stage2/STAGE2_REPORT.md",
        "reports/stage2/TRACEABILITY_MATRIX.md",
        "reports/stage2/G2_ACCEPTANCE.json",
        "src/topoastero/stage2_validation.py",
        "workflows/validate_stage2.py",
        "tests/unit/test_data_model.py",
        "tests/unit/test_acquisition.py",
        "tests/governance/test_stage2_contract.py",
        "tests/governance/test_stage2_schemas.py",
        "tests/integration/test_stage2_cli.py",
    ],
    "software": [
        "README.md",
        "CHANGELOG.md",
        "CITATION.cff",
        "pyproject.toml",
        "uv.lock",
        ".github/workflows/ci.yml",
        ".gitattributes",
        ".editorconfig",
        "docs/reproducibility/CROSS_PLATFORM_PORTABILITY.md",
        "src/topoastero/portability.py",
        "workflows/repair_portability.py",
        "tests/unit/test_portability.py",
        "src/topoastero/__init__.py",
        "src/topoastero/cli.py",
        "workflows/README.md",
        "data/manifests/planned_datasets.yaml",
        "docs/reproducibility/DATA_MANAGEMENT_PLAN.md",
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
    write_csv_lf(
        TARGET,
        rows,
        fieldnames=["deliverable", "path", "size_bytes", "sha256", "status"],
    )


if __name__ == "__main__":
    main()
