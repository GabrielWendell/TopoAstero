# Stage 4 - Analytic cases and stochastic simulation laboratory

## Outcome

G4 passes. Twelve analytic regressions reproduce their exact behavior; the stochastic simulator recovers its registered inputs and distributions; seven null families achieve independent max-statistic calibration; 27 uncertainty cells achieve calibrated coverage; and measured compute costs support the locked confirmation design.

## Task completion

| Task | Evidence |
| --- | --- |
| T4.1 | analytic derivation, 12-case table, unit regressions |
| T4.2 | `topoastero.simulation_lab` oscillator/observation API |
| T4.3 | simulator validation and mode-recovery tables |
| T4.4 | immutable 72-cell balanced fractional pilot matrix |
| T4.5 | seven null generators including IAAFT and real-window nulls |
| T4.6 | max-statistic FWER thresholds; BH-FDR utility; pointwise warning |
| T4.7 | 27-cell split calibration/evaluation coverage map |
| T4.8 | runtime/memory profile and precision-derived compute budget |
| T4.9 | locked confirmation protocol version 1.0 |

## Gate metrics

- Maximum independent null FWER: **0.066** (required <= 0.080).
- Empirical interval coverage: **0.912-0.972** (required 0.900-0.990).
- No population or final-holdout data were used.
- Any representation lacking this calibration remains diagnostic-only or is dropped.
