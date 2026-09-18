# T0.1 - Hypothesis registry

`registries/hypotheses.yaml` is authoritative and testable. This view is for rapid review.

| ID | Positive claim | Null/failure | Primary comparison | Minimum publishable result |
| --- | --- | --- | --- | --- |
| H1 | Normalized-PSD H0 persistence estimates `nu_max`/envelope strength stably | No error, calibration, robustness, or QC gain after matched preprocessing | pySYD/Lightkurve and prominence/background controls | Calibrated improvement/noninferiority plus QC, or bounded redundancy/failure |
| H2 | Cylindrical ridge persistence peaks near physical `Delta_nu` and rejects aliases | Classical or graph-only controls match it; smoothing/order choices dominate | ACF/PSPS and periodic topology-free ridge score | Correct-spacing operating domain or explicit alias/redundancy map |
| H3 | Persistent ridge geometry recovers one locked small-separation ratio | No candidate reaches error/coverage criterion beyond frequency fitting | Peak-bagged/conventional fit and circular-statistics control | One calibrated ratio domain or rigorous no-estimate boundary |
| H4 | Delay H1 contains phase/coherence information beyond the PSD | Phase-randomized/IAAFT surrogates reproduce it | PSD-only model and PSD-preserving surrogates | Phase-sensitive effect or strong negative result |
| H5 | Locked topology features add conditional out-of-sample value | No practical gain after classical variables | Identical-fold classical-only, topology-only, and shuffled-topology models | Gain/QC beyond frozen margin or powered equivalence statement |
| H6 | Stability results yield useful astrophysical bounds | Bound invalid or uniformly too loose to change a decision | Direct perturbation Monte Carlo and generic stability bound | Useful bound, exact limited identity, or counterexample |

Every record also specifies estimand, unit of analysis, metric direction, required companions,
nulls, falsification rule, linked RQs/objectives, decision stage, and which numerical choices remain
scheduled for a non-holdout pilot.

## Objective treatment

O1-O10 and RQ0-RQ9 are exhaustively cross-referenced in
`registries/objective_crosswalk.yaml`. O1 (classical reproduction) and O10 (open/reproducible
release) are operational scientific controls rather than forced statistical hypotheses; each has a
failure condition, baseline, unit, and minimum conclusion. This distinction prevents a software
deliverable from being mislabeled as an empirical hypothesis while still making it falsifiable at
the gate level.

