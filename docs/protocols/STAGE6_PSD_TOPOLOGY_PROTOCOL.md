# Stage 6 PSD-topology protocol

**Protocol:** `TA-STAGE6-PSD-1.0`  
**Run:** `TA-S06-PSD-R001`  
**Status:** locked before execution

## Inputs and split

The 72 Stage 4 factorial cells are deterministically reused with independent Stage 6 seed streams.
Odd cell numbers calibrate interval behavior and even cell numbers evaluate it. No LEGACY
population member, development star, internal-validation star, or final-holdout star is opened.

## Registered analyses

1. Compare all four spectrum normalizations and retain `log(P/B)` as primary.
2. Compute exact localized superlevel `H0`, including endpoints and the undying essential class.
3. Audit lifetime/prominence identity on analytic and realistic spectra with an independent scan.
4. Compare persistence centroid, robust locations, smoothed envelope, and the explicitly labeled
   pySYD-style control; validate the external-pySYD result adapter.
5. Score a common spacing grid with persistence differences, persistence autocorrelation, ACF, and
   PSPS, while retaining half/nominal/double alternatives.
6. Calibrate maxima across all searched frequencies and spacings using disjoint seed streams.
7. Recompute diagrams and estimates under background, smoothing, resolution, and window branches.
8. Apply all five nonexclusive quality flags without dropping failed cells.

## Primary metrics

`nu_max` comparisons report bias, median absolute error, 95% coverage, and catastrophic failures.
Comb comparisons report correct-spacing recovery, half/double alias outcomes, and whether incorrect
or ambiguous results were captured by a reason code. Results are paired and summarized overall and
by duration, S/N, duty cycle, and lifetime.

## Gate interpretation

G6 may pass with an equivalence-limited claim. False-alarm and false-confidence rates must be at or
below 0.08; evaluation coverage must be at least 0.85; every incorrect/ambiguous spacing outcome
must be explicitly represented and at least 85% must receive the registered ambiguity flag; and
reliable rows must have a catastrophic `nu_max` rate at or below 0.10. Exact prominence equivalence
removes an inferential-novelty claim but does not invalidate the stable localization/API contribution.
