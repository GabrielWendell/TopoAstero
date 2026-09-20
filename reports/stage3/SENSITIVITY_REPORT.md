# Window, background, preprocessing, and uncertainty sensitivity

## Background

The zero-component white model is decisively inadequate. Adding one Harvey-like component reduces
BIC from 950092 to 847833; the two-component model reduces it to 845384 and has the smallest log
residual RMS (0.1033). The H2 covariance condition (148.5) is finite but warns that component
parameters are correlated; parameter errors are therefore pipeline approximations, not a physical
posterior.

## Window and stitching

Individual-quarter duty cycles are 0.962-0.977, with Rayleigh resolution 0.122-0.427 uHz. Keeping
the physical Q2-to-Q7 timestamps gives 488.18 days, 0.02371-uHz resolution, and duty cycle 0.6006.
Compressing quarters gives 301.03 days and duty cycle 0.9740 but changes the alias pattern; it is
retained only as a diagnostic. Absolute timestamps are the primary choice.

## Preprocessing

| Branch | `numax` (uHz) | `dnu` (uHz) | Role |
| --- | ---: | ---: | --- |
| tutorial PDCSAP/default | 2145 | 103.112 | primary |
| PDCSAP/quality-zero/clip | 2175 | 102.946 | sensitivity |
| SAP/high-pass/clip | 2175 | 102.543 | sensitivity |
| PDCSAP/hardest/clip | 2175 | 102.946 | sensitivity |
| independent H2/ACF | 2231.569 | 103.366 | pipeline comparison |

The frozen half-ranges, 43.284 uHz and 0.412 uHz, become pipeline-choice uncertainty. None of these
branches was chosen after viewing a topological statistic or a topological echelle.

## Uncertainty

Ten monthly segments are resampled 500 times with seed 20260721. The bootstrap is intentionally
wide for `numax` (`sigma=93.78 uHz`, 16th-84th percentiles 2141.2-2372.48 uHz) and tight for the
comb spacing (`sigma=0.0962 uHz`, percentiles 103.225-103.389 uHz). Reference disagreement stays a
separate column. Scaling-relation uncertainties include Teff, but do not include unmodeled scaling
calibration systematics and must not be interpreted as definitive stellar-property errors.

Full precision, model likelihoods, aliases, branch outputs, and uncertainty components are in the
four corresponding CSV tables under `results/stage3/`.
