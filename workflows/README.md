# Workflows

Workflow files are thin, unattended entry points. Scientific logic lives in the package and is
unit-tested; notebooks call the same functions and are never authoritative.

- `smoke.py`: seeded analytic signal -> H0 persistence -> tables, figure, and manifest.
- `validate_stage0.py`: validates all frozen governance records and smoke evidence.
- `build_stage1_benchmarks.py`: checksum-verified publisher tables -> LEGACY/Rudy CSV evidence.
- `build_stage1_manifest.py`: rebuilds the Stage 1 deliverable checksum index.
- `validate_stage1.py`: validates all T1.1-T1.8 records, the G1 gate, and Stage 0 regression.
- `query_stage2_mast.py`: re-runs the dated Rudy MAST queries and inspects cached FITS payloads.
- `query_legacy_kepler_inventory.py`: freezes archive candidates for all 66 LEGACY stars.
- `acquire_stage2_products.py`: downloads and checksum-verifies frozen mission products.
- `build_stage2_reference_data.py`: checksum-verified publisher/Stage 1 sources -> canonical references.
- `build_stage2_examples.py`: creates canonical JSONL fixtures including a verified Q2 excerpt.
- `build_stage2_partitions.py`: regenerates the deterministic star-grouped partition and seal.
- `build_stage2_qc.py`: derives the pre-topology machine QC report.
- `build_stage2_manifest.py`: rebuilds the Stage 2 deliverable checksum index.
- `validate_stage2.py`: validates T2.1-T2.8, G2, and all earlier-stage regressions.
