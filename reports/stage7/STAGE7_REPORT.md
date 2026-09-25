# Stage 7 - Delay-embedding topology and phase-information test

## Outcome

G7 **passes** with decision **DROP** and claim `calibrated_negative_result`. Delay PH is dropped from the critical path: neither PSD-preserving-null rejection nor predictive increment met the frozen threshold.

## Evidence boundary

The stage uses 24 sealed simulation cells with independent odd/even calibration and evaluation
roles. Population data and the final holdout were not opened. PCA appears only in a visualization;
all persistence was computed on unreduced delay clouds.

## Gate evidence

- Evaluation BH rejection rate, phase-randomized: **0.000**.
- Evaluation BH rejection rate, IAAFT: **0.000**.
- Combined lifetime-prediction improvement over classical controls: **-0.136**.
- Median normalized convergence bottleneck at 15 versus 18 landmarks: **0.0902**.

Both positive and calibrated-negative outcomes were admissible before execution. The serialized
decision follows the frozen rule without post-evaluation threshold changes.
