# Stage 5 representation selection memo

## Locked decision

Proceed with **REP-DELAY, REP-PSD, REP-ECHELLE**. Preserve without a primary claim or drop **REP-LC, REP-MODE**. The exact reasons and criterion states are frozen in `registries/stage5_selection.yaml`; no failed implementation was deleted.

- REP-PSD contributes a localized maximum and conditional persistence-weighted frequency centroid to Stage 6, with background null and prominence/envelope controls.
- REP-DELAY contributes only maximum H1 persistence, explicitly exploratory, to the Stage 7 phase/IAAFT surrogate test. Passing G5 does not assert phase information.
- REP-ECHELLE contributes H0 ridge lifetime on the correct cylindrical domain to Stage 8, paired with circular-ridge controls.
- REP-LC stays available for morphology diagnostics but is not a p-mode comb estimator.
- REP-MODE is dropped from the critical path because it depends on extracted modes and is redundant with simpler geometry and the echelle route.

The maximum independent evaluation false-positive rate across all five representation nulls is **0.078** (screening limit 0.125). Visual interest played no role.
