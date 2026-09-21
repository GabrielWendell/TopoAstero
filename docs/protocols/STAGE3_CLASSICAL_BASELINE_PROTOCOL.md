# Stage 3 classical baseline and observation-model protocol

**Protocol:** CBOM-1.0  
**Frozen:** 2026-09-20  
**Configuration:** `configs/stage3_classical.yaml`  
**Run:** `TA-S03-T01-RUDY-R001`

## Scope and non-topological firewall

This protocol implements T3.1-T3.9 for Rudy (KIC 10963065). It fixes the classical observation
model before any Stage 4 topology is inspected. Every preprocessing branch has
`selection_basis=classical_predeclared_no_topology`; the Stage 3 workflow imports no persistence or
topological estimator. Rudy remains a descriptive benchmark and no population holdout is opened.

Raw FITS files are authoritative at MAST and are not redistributed. The one-command workflow reads
the 10 checksum-sealed Kepler short-cadence products from Q2/Q5/Q6/Q7 and the 11 homogeneous SPOC
two-minute TESS products from an external cache. `--download` acquires only those frozen product
identities and verifies size plus SHA-256 before analysis:

```bash
uv run --extra astronomy python workflows/run_stage3_classical.py \
  --cache-dir /absolute/path/to/topoastero-cache --download
```

Offline audit does not contact MAST:

```bash
uv run topoastero validate-stage3 --root .
```

## Figure visual contract

All six Stage 3 figures use `topoastero.style` visual contract `TA-PLOT-1.0` in its reproducible
`paper` context with TeX disabled. The workflow exports figures through `save_figure`, which embeds
the software version, style ID, and machine-readable source in deterministic SVG metadata. Stable
colors distinguish raw spectra, fitted backgrounds, mode degree, sampling-window treatment, and
TESS outcome; marker and line styles retain the key categorical distinctions without color alone.
The complete policy is `docs/reproducibility/PLOTTING_STYLE_GUIDE.md`.

## T3.1 Lightkurve reproduction

The primary branch is the official tutorial operation: read PDCSAP flux with Lightkurve's default
quality mask, normalize each returned monthly file during `LightCurveCollection.stitch()`, retain
absolute BKJD sampling gaps, calculate a Lomb-Scargle one-sided PSD from 1500-2700 uHz, apply the
default log-median flattening, and estimate `numax`/`dnu` with ACF2D. The tutorial solar references
are 3090 uHz, 135.1 uHz, and 5777.2 K. Scaling-relation mass, radius, and log g are validation
products, not physical ground truth.

## T3.2 independent estimator and convention reconciliation

`TA-HARVEY-ACF-v1` starts from the same primary stitched light curve but does not call a Lightkurve
seismic estimator. It converts the PSD to `ppm^2/uHz`, chooses a background by BIC, smooths the
whitened envelope by 35 uHz, and locates its maximum over 1700-2500 uHz. It estimates the large
separation from an FFT autocorrelation over `numax +/- 275 uHz`, after 0.5-uHz smoothing, searching
within 0.75-1.25 times the Stello scaling prediction. A parabolic three-bin interpolation removes
frequency-bin-edge quantization.

Both pipelines use frequency in uHz, a one-sided power spectral density, absolute timestamps, and
the same input payloads. Their difference therefore represents background/estimator choice rather
than a hidden unit, sidedness, cadence, or data-selection mismatch.

## T3.3 background model

The compared family is

`B(f) = W + sum_j A_j / (1 + (f / f_j)^4)`,

with zero, one, or two Harvey-like components plus white noise. The 1500-2800-uHz oscillation region
is excluded from fitting. Log-frequency-bin medians are divided by `ln(2)` to estimate the mean of
exponential periodogram ordinates; all retained raw ordinates then enter the exponential likelihood
`sum(log B + P/B)`. The report retains likelihood, AIC, BIC, log-residual RMS, covariance condition,
and approximate log-parameter errors for every model, including rejected models.

## T3.4 sampling window

For each quarter and for the combined observations, cadence occupancy is placed on the native
58.84876286-second grid and transformed as `|FFT(mask)|^2 / N_observed^2`. The atlas records duty
cycle, Rayleigh resolution, and three strongest resolved aliases. Absolute-time combination is
primary. A compressed-quarter diagnostic is retained only to expose the aliases that would be
changed by deleting the physical inter-quarter gaps.

## T3.5 conventional echelle

Three trial spacings (103.110, 103.179, and 103.323 uHz) use the same 1500-2800-uHz whitened PSD,
128 phase bins, increasing frequency from bottom to top, increasing modulo-frequency from left to
right, and a Gaussian phase smoothing kernel with a circular left/right boundary. Partial first and
last orders remain visibly missing; they are not filled or reflected.

## T3.6 mode audit

All 42 published Rudy `(n,l)` rows are overlaid. Each row is matched to the greatest whitened PSD
ordinate within a frozen +/-2.5-uHz window. The residual is measured-minus-published frequency.
Echelle order is `floor(frequency/dnu)` and its offset from the publisher's radial-order label is
reported explicitly; order labels are never silently relabeled.

## T3.7 preprocessing branches

`registries/preprocessing_branches.csv` freezes PDCSAP/SAP choice, quality masks, detrending,
outlier treatment, gap treatment, stitching, spectral method, and PSD normalization. Four Kepler
branches are executed; the uniform analytic FFT branch tests units; the TESS branch forbids
cross-sector stitching. No branch is selected by an echelle image or a topological statistic.

## T3.8 uncertainty decomposition

Random uncertainty is the standard deviation of 500 nonparametric resamples of the ten monthly
Kepler segments on a common 0.1-uHz grid. Pipeline-choice uncertainty is half the full range across
the four executed preprocessing branches and the independent estimator. Published interval
half-width is retained separately as reference disagreement. The three components are combined in
quadrature only for the G3 joint-agreement check; the component columns remain authoritative.
Scaling-relation random errors include the 77-K temperature uncertainty by first-order propagation.

## T3.9 TESS feasibility rule

Each SPOC two-minute sector is analyzed alone. A result is only a marginal candidate when the
smoothed envelope ratio is at least 1.20, candidate `numax` is within 150 uHz of the Kepler
first-look result, candidate `dnu` is within 10 uHz, and the ACF peak is at least 0.08. A marginal
candidate is not confirmation. Stage 3 does not combine sectors for detection; any later
combination must predeclare cadence/author compatibility and a window model.

## G3 interpretation

G3 passes when the tutorial is numerically reproduced, global results overlap defensible
references under the recorded joint uncertainty or have a traced convention/model explanation,
PSD units pass Parseval and sinusoid injection tests, background injection/model-selection tests
pass, every figure has a machine-readable source, and TESS non-detections are retained. A failure
in PSD normalization or background injection blocks Stage 4.
