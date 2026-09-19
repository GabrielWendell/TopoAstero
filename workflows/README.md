# Workflows

Workflow files are thin, unattended entry points. Scientific logic lives in the package and is
unit-tested; notebooks call the same functions and are never authoritative.

- `smoke.py`: seeded analytic signal -> H0 persistence -> tables, figure, and manifest.
- `validate_stage0.py`: validates all frozen governance records and smoke evidence.
- `build_stage1_benchmarks.py`: checksum-verified publisher tables -> LEGACY/Rudy CSV evidence.
- `build_stage1_manifest.py`: rebuilds the Stage 1 deliverable checksum index.
- `validate_stage1.py`: validates all T1.1-T1.8 records, the G1 gate, and Stage 0 regression.
