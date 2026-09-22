# Stage 5 representation audit protocol

**Protocol:** TA-S05-AUDIT-1.0  
**Frozen:** 2026-09-22 before population-level topological analysis  
**Inputs:** Stage 4 exact cases and 72 simulation-development cells

## Purpose and separation

The audit chooses a small, interpretable candidate set for Stages 6-8. It is not a population
validation and it cannot support stellar-performance claims. Rudy remains descriptive; the
LEGACY development, validation, and final-holdout partitions are barred. All negative and dropped
representations remain in the repository.

## Prespecified execution

1. Run exact and independent-backend cross-checks at tolerance \(10^{-10}\).
2. Evaluate all five representations on the same 72 frozen Stage 4 pilot cells.
3. Calibrate each registered maximum statistic on 64 null realizations and estimate false-positive
   rate on a separate 64-realization stream. Use plus-one p-values.
4. Audit amplitude scaling, additive offset, monotone transformation, cadence, sample density,
   embedding dimension, PSD smoothing, grid resolution, and periodic boundary handling.
5. Compute pairwise Spearman association and the Gaussian-copula mutual-information proxy on the
   development panel. The latter is descriptive, not a general nonlinear-information proof.
6. Compare deterministic six-fold classical-only and classical-plus-topology ridge models on
   matched targets. These are selection diagnostics, not final predictive estimates.
7. Apply interpretability, calibration, incremental utility, numerical stability, compute, and
   later-role criteria. Lock statuses and reasons in `registries/stage5_selection.yaml`.

## Nuisance decisions

Amplitude and offset invariance are exact requirements after robust normalization. Other ordinary
perturbations pass this screening audit when the registered scalar changes by at most 60%; larger
effects force diagnostic-only or dropped status unless a later stage explicitly models that
nuisance. The periodic-boundary audit is directional: a correct cylinder must contain one
essential H1 class, while the same rectangular grid must contain none. Detecting that change is a
pass, not instability.

## Retention rule

A retained statistic must have all of the following:

- a named physical target and a localized interpretation;
- an independently evaluated, nuisance-matched null;
- a simpler non-topological control;
- deterministic numerical behavior and a passed relevant sensitivity audit;
- bounded compute under the registered pilot resolution; and
- a prespecified role in Stage 6, 7, or 8.

Incremental development utility breaks ties and can narrow the candidate set. An exploratory
delay statistic may proceed only to the explicit Stage 7 PSD-preserving retain/drop test; this is
not evidence for a phase-sensitive claim. Visual interest is never a retention criterion.

## Multiplicity and deviations

The null statistic is the maximum over every summary registered for that representation at this
stage. Later parameter searches require new family-wise calibration across their full search
space. Any altered lag, landmark count, smoothing, metric, grid, or selection threshold is a
versioned deviation and cannot silently replace this locked audit.

