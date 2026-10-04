# Stage 11 implementation validation

Validated with the unchanged locked environment on Python 3.12.14.

| Check | Result |
| --- | --- |
| Full pytest suite | 397 passed, 0 failed |
| Branch-aware total package coverage | 85.04% (required: 85%) |
| Ruff | PASS |
| Strict mypy | PASS, 45 source files |
| Source distribution and wheel build | PASS |
| Repository portability | PASS |
| Stage 0–11 implementation validators | PASS |
| Stage 11 raw non-holdout reproduction | PASS for supplied acquisition snapshot |
| Stage 11 reduced replay | PASS for 1 observational star (Rudy) |
| Paper II LaTeX/BibTeX compile | PASS; 2 pages inspected |
| Four figure sets | PNG/SVG/PDF generated and inspected |
| Stage 10 portable raw-data reproduction | PASS for 46 scientific, figure and manuscript files |

Executable commands and dependency instructions are in `docs/reproducibility/STAGE11_REPRODUCTION.md`. Test cases include explicit synthetic fixtures for signing, source/payload tampering, failed checkpoints, interruption/resume, role isolation, corrected-reference import, statistical edge cases and missing-input reporting. Synthetic fixtures never open or substitute for the research holdout.

The scientific G11 status remains `population_pending`: 10 of 2,159 candidate Kepler products are available, only Rudy has observational estimates, and no confirmation release/opening has occurred. Full acquisition, actual supervisor/steward authorization, a real container image digest, an exact signed release and one-time confirmation execution are outstanding scientific execution steps. The provided Dockerfile was not built locally. No population performance, publication readiness or independent human review is asserted.

The supplied Stage 10 archive needed administrative seal/reproduction repairs. The original strict-check failure and the successful separate portable check are retained. See `INHERITED_REPAIRS.md`; earlier numerical science and core source files are unchanged.

The existing CI matrix covers Python 3.11, 3.12 and 3.13; only Python 3.12.14 was executed here.
