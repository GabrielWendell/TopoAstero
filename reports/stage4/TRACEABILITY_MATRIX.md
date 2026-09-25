# Stage 4 traceability matrix

| Task | Requirement | Primary implementation | Executable/recorded evidence |
| --- | --- | --- | --- |
| T4.1 | Prove exact cases and assumptions | `docs/derivations/STAGE4_ANALYTIC_CASES.md`, `topoastero.persistence`, `topoastero.simulation_lab` | 12 rows in `results/stage4/analytic_cases.csv`; analytic unit tests |
| T4.2 | Stochastic damped-mode simulator | `src/topoastero/simulation_lab.py` | seeded periodogram and time-domain API tests |
| T4.3 | Validate target PSD, mode parameters, variance, cadence | `workflows/run_stage4_simulation_lab.py` | `simulator_validation.csv`, `mode_recovery.csv`, simulator figure/report |
| T4.4 | Factorial pilot | `configs/stage4_simulation.yaml` | immutable 72-cell `registries/stage4_factorial_design.csv` and complete pilot table |
| T4.5 | Nuisance-matched null families | seven generators in `simulation_lab.py` | null unit tests and seven-family calibration table |
| T4.6 | Multiplicity control | max statistic, empirical p-value, and BH-FDR functions | independent thresholds and FWER table; pointwise rows marked diagnostic-only |
| T4.7 | Coverage and bias | split calibration/evaluation workflow | 27-cell coverage table and coverage figure |
| T4.8 | Runtime, memory, caching, and repetition budget | traced benchmark and binomial MCSE functions | 12-cell compute table, precision budget, compute figure |
| T4.9 | Freeze confirmation | machine-readable locked protocol | protocol tests, run manifest, G4 record |

## Deliverables

| Deliverable | Evidence |
| --- | --- |
| D4.1 Analytic regression suite and derivation | derivation note, 12-case CSV, unit tests, analytic figure |
| D4.2 Validated simulator | package API, science note, validation/recovery tables, sample light curve and spectrum |
| D4.3 Registered simulation/null design and immutable pilot archive | frozen config, 72-cell registry, real-window table, null calibration, run manifest |
| D4.4 Detection, bias, coverage, and runtime maps | factorial results, thresholds, coverage and compute tables, six figures, reports |
| G4 | `G4_ACCEPTANCE.json`, validator, CLI/CI enforcement, deliverable SHA-256 manifest |

The numerical run manifest seals every workflow-produced Stage 4 result, report, and figure that
existed when the run completed. The deliverable manifest separately seals source, governance,
schema, test, and acceptance artifacts. Raw Kepler and TESS payloads remain external.
