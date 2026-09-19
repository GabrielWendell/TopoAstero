# Stage 1 traceability matrix

The controlling specification is Chapter 3, pages 13-14 of the detailed agenda. Machine-readable
tables are authoritative; prose explains their intended use and boundaries.

| Task | Implementation evidence | Automated acceptance | Status |
| --- | --- | --- | --- |
| T1.1 Physics map | `physics_matrix.csv`; `SOLAR_LIKE_PHYSICS_MAP.md` | required columns; source-key resolution; physics implications present | Complete |
| T1.2 Classical pipelines | `classical_baseline_matrix.csv`; `CLASSICAL_PIPELINE_MAP.md` | exact CB-01..CB-08; all H1-H6 crosswalk entries resolve | Complete |
| T1.3 Rudy evidence | identity YAML; 276-row target sheet; 42-row mode table; Rudy specification | aliases; exact authoritative `numax`/`dnu`; mode count/uniqueness/numeric bounds | Complete |
| T1.4 LEGACY population | 66-row population sheet; LEGACY specification; provenance | exact unique star count; Rudy membership; all four authoritative targets per star | Complete |
| T1.5 Mathematical TDA | `theorem_matrix.csv`; `MATHEMATICAL_TDA_MAP.md` | exact TDA-01..TDA-09; assumptions and non-claims required | Complete |
| T1.6 Astronomy TDA | `astronomy_tda_gap_map.csv`; adjacency note | directness and transfer limits required; source-key resolution | Complete |
| T1.7 Novelty audit | 18 execution rows; audit protocol; gap memorandum | six concepts; two complete services; failures cannot count as zero; no unreconciled direct precedent | Complete with bounded conclusion |
| T1.8 Reference validation | clean BibTeX; claim-level audit; quarterly protocol; four JSON Schemas | audit/BibTeX key equality; DOI uniqueness; verified metadata; all evidence sources resolve | Complete |

## Deliverables

| Deliverable | Primary artifact | Acceptance evidence |
| --- | --- | --- |
| D1.1 Structured literature matrix | `evidence/literature/literature_matrix.csv` plus five specialist matrices | 25 synthesis records covering T1.1-T1.8 and resolvable sources |
| D1.2 Research-gap memorandum | `docs/literature/RESEARCH_GAP_MEMORANDUM.md` | separates established plausible and candidate-novel claims; redefinition rule explicit |
| D1.3 Benchmark target specification | `evidence/benchmarks/benchmark_targets.csv` | 264 authoritative targets and 12 clearly marked context-only rows; units/uncertainty/source/reconciliation |
| D1.4 Verified bibliography | `topoastero_stage1.bib`; `reference_audit.csv` | 35 key-matched entries and quarterly protocol |

## Gate G1

| Clause | Evidence |
| --- | --- |
| Reproducible search finds no duplicate direct precedent | exact URLs/dates/statuses in novelty log; screening test and limitations in audit |
| Every benchmark number traceable | long-form target fields; mode-table source columns; publisher snapshot hashes |
| At least one classical baseline per topological claim | H1-H6 crosswalk and baseline catalog |
| Direct precedent causes redefinition | mandatory five-step rule in research-gap memorandum |

`G1_ACCEPTANCE.json` is the machine decision. Validation also re-runs the complete Stage 0 contract,
including the unopened final-holdout log.

