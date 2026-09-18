# Workflows

Workflow files are thin, unattended entry points. Scientific logic lives in the package and is
unit-tested; notebooks call the same functions and are never authoritative.

- `smoke.py`: seeded analytic signal -> H0 persistence -> tables, figure, and manifest.
- `validate_stage0.py`: validates all frozen governance records and smoke evidence.

