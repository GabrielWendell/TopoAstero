# Stage 4 simulation and null-calibration protocol

Protocol `TA-STAGE4-SIMULATION-1.0` is frozen by `configs/stage4_simulation.yaml`. The run identifier
is `TA-S04-LAB-R001`. No population or final-holdout topological result was used to select its
factors, thresholds, endpoints, or tolerances.

## Registered sequence

1. Run exact analytic regressions before stochastic experiments.
2. Validate the stochastic oscillator against its target PSD, exponential statistics, input mode
   parameters, time variance, and cadence response.
3. Execute all 72 pilot cells. Numerical failures remain failures and are never silently removed.
4. Calibrate each null family on 256 realizations and evaluate it on 256 disjoint seeds.
5. Use the maximum statistic over all trial spacings, smoothing scales, and summaries for FWER.
   Pointwise thresholds are illustrative and cannot support a confirmatory claim.
6. Calibrate uncertainty intervals on 320 realizations and assess coverage on 320 new realizations
   in each of 27 S/N-duration-lifetime cells.
7. Measure runtime and traced memory, then derive repetitions from Monte Carlo standard-error
   targets rather than convenient round numbers.
8. Lock the confirmation protocol before population analysis.

## Factorial pilot

The balanced fractional matrix covers high, medium, and low S/N; four durations corresponding to a
TESS sector, a Kepler quarter, multiple sectors/quarters, and a long baseline; three cadences; duty
cycles near 0.5, 0.8, and 0.95; three values each of $\nu_{\max}$, $\Delta\nu$, lifetime, visible
orders, and ridge curvature; correct and misspecified backgrounds; no, random, Kepler, and TESS gap
families; and the $\Delta/2$ and $2\Delta$ aliases. It is a pilot operating map, not a full Cartesian
claim.

Every listed factor is operative. The alias factor inserts an interleaved half-spacing comb or
removes alternating orders for the double-spacing case. Duty cycle raises the effective noise
floor, random gaps introduce local leakage, and the Kepler/TESS cells add mission-specific alias
pairs with weights set by the requested and payload-template duty cycles. The exact time-domain API
can instead apply every interval in the payload-derived mask; the fractional pilot uses the stated
frequency-domain proxy to keep all 72 cells computationally bounded.

## Nulls and multiplicity

The registered null families are background-only, randomized comb, white noise, red noise,
phase-randomized, IAAFT, and real-window. Phase randomization preserves Fourier amplitudes; IAAFT
also preserves the empirical amplitude distribution. The real-window family uses a payload-derived
TESS mask. A nuisance family cannot borrow a more favorable threshold from another family.

The primary rule controls FWER using an independently calibrated row maximum. The package also
implements Benjamini-Hochberg FDR for explicitly designated secondary families. Neither an
uncorrected pointwise p-value nor a threshold selected after viewing the evaluation stream is
confirmatory.

## Uncertainty and stopping

Realization scatter and pipeline-choice scatter are stored separately and combined only by an
explicit rule. Equal-tailed absolute-error intervals use a calibration/evaluation split. Accepted
coverage is 0.90 through 0.99 for nominal 0.95 intervals; both undercoverage and extreme
overcoverage fail.

Every registered cell is completed. There is no significance-based early stopping. Integrity,
safety, or resource incidents may stop the run, but require a deviation record. Material protocol
changes require a new version and new run identifier.
