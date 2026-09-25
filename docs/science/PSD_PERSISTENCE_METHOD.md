# Persistent topology of the power spectrum

## Scope

Stage 6 applies exact zero-dimensional superlevel persistence to a background-normalized power
spectrum. The primary scalar field is `log(P/B)`, where `P` is a positive PSD ordinate and `B` is
the registered positive background estimate. `P/B`, `P/B - 1`, and an uncertainty-aware z-score
are frozen sensitivities. The method rejects, rather than silently clips, nonpositive inputs.

## Exact localized classes

The frequency bins form a path graph. Vertices enter from high to low scalar value; when components
merge, the lower-born component dies. Equal births are resolved by lower frequency-bin index.
Endpoints can birth ordinary classes. The oldest class is essential and is kept for localization,
but it receives no artificial death and is excluded from numerical lifetime summaries. Every
finite record contains both its birth frequency and merge-saddle frequency.

## Prominence identity and claim limit

On this domain, finite `H0` lifetime is exactly elder-rule peak prominence when both methods use
the same boundary, tie, and essential-class rules. TopoAstero verifies the equality with a separate
path scan that does not call the persistence backend. Therefore Stage 6 does not claim that path
`H0` creates a new peak-strength statistic. Persistence is retained as a deterministic
organization/localization layer for uncertainty propagation and downstream estimator bookkeeping.

## `nu_max` and uncertainty

The primary location is the persistence-weighted centroid of finite peak birth frequencies inside
the registered search band. Weighted-median and Huber locations are sensitivities. Uncertainty is
obtained by rerunning peak construction and location on posterior-predictive or bootstrap spectra;
the locked simulation gate applies a preregistered minimum interval width in units of `Delta nu`.
A topology-free smoothed envelope and an offline pySYD-style Gaussian-envelope control are evaluated
on the same spectra. A validated adapter accepts genuine external pySYD results. The style control
is never represented as an execution of the pySYD package, and a population comparison requires
genuine external results.

## Comb candidates

Persistence weights enter both a frequency-difference kernel and a weighted autocorrelation. The
API always returns `Delta nu / 2`, `Delta nu`, and `2 Delta nu` alternatives with scores and ranks.
It does not silently force the nominal branch. ACF and a sinusoidal PSPS score are computed without
topology on the identical trial grid.

## Calibration and failure behavior

Envelope and comb thresholds use independent calibration/evaluation streams. Each null realization
is reduced to the maximum over the complete registered frequency/trial family before thresholding.
The five nonexclusive reason codes are `absent_envelope`, `alias_ambiguity`,
`insufficient_orders`, `window_contamination`, and `unstable_background`. Every failure remains in
the denominator and the result table.

