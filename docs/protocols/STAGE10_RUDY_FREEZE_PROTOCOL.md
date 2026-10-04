# Stage 10 - Rudy and Paper I freeze

Protocol **TA-STAGE10-RUDY-1.0**, run **TA-S10-RUDY-R001**, 2026-10-01.
The implementation lock precedes the new Stage 10 topology/null analysis, but
is not an externally timestamped preregistration. Stage 3 descriptive Rudy
results were already inspected. No population data or final holdout is permitted.

## T10.1 - Frozen observation capsule

Use the ten checksum-verified Kepler tutorial SC products (Q2/Q5/Q6/Q7) and
eleven homogeneous SPOC two-minute TESS sectors in the Stage 2 manifests. Public
MAST URIs, payload SHA256/size, time reference, flux/quality columns and exposure
metadata are copied into `benchmark_capsule.json`. Raw payloads remain outside
the release. Quality mask integer constants from the locked Lightkurve installation
and per-product retained-cadence counts are recorded. PP-01 is primary, PP-02/03/04
are mandatory sensitivities, PP-05 is analytic validation, PP-06 is transfer.
The branch definitions remain those of `registries/preprocessing_branches.csv`.

## T10.2/T10.3 - Baseline and localized spectral persistence

Reproduce the original Lightkurve default tutorial separately from the independently
implemented Harvey/ACF pipeline. Preserve absolute timestamps and normalize each
month. Remove nonfinite flux rows consistently before analysis. Fit Harvey families
with zero, one and two components outside 1500-2800 microHz; primary choice is
minimum BIC. BIC is descriptive because retained LS ordinates can be correlated.
Mean-rebin the native PSD on 0.2-microHz centers. Resolution sensitivities interpolate
only when the requested grid is finer than native resolution; no information is added.

Smooth power at 1 microHz before exact path H0 and use log(P/B) as primary.
Keep ratio, residual and registered 10%-background-allowance z-score sensitivities.
Essential classes are localized and omitted from numeric summaries. Check exact
elder-rule prominence equivalence with an independent implementation. The centroid
is a diagnostic whose Rudy coverage has not been calibrated. Search all 57 comb
trials from 20 to 300 microHz and retain ACF/PSPS controls and boundary/alias flags.

## T10.4/T10.5 - Cylinder and delay decision

Use the G8 24-phase-bin periodic complex and fixed 0.55 finite-H0 / 0.45 graph score.
Scan half, nominal and double families at five relative spacings; the primary
classical ACF supplies the anchor, never the published spacing. In the null ensemble
each realization uses its own classical ACF anchor, preserving the adaptive policy.
Conventional fold contrast, Hough and graph controls remain visible across all four
preprocessing and three Harvey families. The Stage 8 normalization remains log(P/B);
the four alternative normalizations are audited for the spectral construction.
No blind degree identification, topological frequency ratios, utility or calibrated
cylindrical confidence interval is authorized under G8's geometry_only decision.
Published identified modes are overlaid and formula checked, with their external
provenance retained. G7's drop decision omits Rudy delay PH and reports the negative result.

## Conditional nulls and multiplicity

Generate 256 independent stationary Gaussian Harvey-background signals on a full
58.84876286-second grid spanning the observed Kepler times. Scale generative density
by measured cadence-mask duty to reconcile full-span LS and retained-exposure white
noise conventions. Correct the analytically averaged two-tap interpolation power
response before drawing the uniform-grid signal. The initial implementation's
mean null P/B was 0.901; this validation-led nuisance repair is recorded before
the final freeze and every registered result is regenerated. Interpolate to actual barycentric timestamps, use the same
native LS, rebin and smoothing, and retain per-realization search maxima.
This is an approximate discretized observation operator; it does not fit nonlinear
pipeline or instrumental systematics. Record ensemble mean P/B as a model diagnostic.
The fitted background is held fixed, so every p-value is conditional on that fit.
No raw-bin Gamma bound from Stage 9 is applied to these smoothed spectra.

Use plus-one upper-tail counts, MC standard error and Wilson intervals for the
underlying exceedance rate. Apply Holm across the seven reported statistic families.
Minimum attainable unadjusted p is 1/257; 256 draws were chosen before observing
null results so seven times that value is below alpha=0.05. This remains a finite
Monte Carlo calculation, not precision sufficient for extremely small false alarms.

## T10.6 - Uncertainty targets

Analyze quarters separately and cumulative absolute baselines, holding the primary
background fixed to isolate observed sampling/realization differences. These results
are converted to the full-span density convention using segment-duty/full-duty
before whitening with that background. The corresponding scale is applied to
each monthly PSD before resampling. The quarterly and cumulative results
overlap and are not independent stellar observations. Resample ten disjoint monthly
PSDs 256 times and average by retained cadence counts. The resulting intervals target
the monthly-averaged-spectrum estimator, not the coherent full-span LS estimator.
Report 64 conditional Gaussian stochastic repeats of a smoothed observed PSD separately.
Use 64 monthly echelle bootstrap draws as alias/ridge diagnostics, never validated CIs.
Keep seismic/temperature scaling calculus, pipeline ranges and unquantified stellar
scaling-systematic allowances separate. Do not issue a physical stellar posterior.

## T10.7/T10.8 - Transfer and robustness

Degrade Q5 at three source offsets using exact integrals of its piecewise-linear
curve through ideal 120-second boxcars, rejecting any exposure across a source gap
larger than 180 seconds. Apply all eleven actual TESS retained-timestamp windows,
13.7/27.4-day duration cuts, extra retained fractions 1/0.8, and noise variance factors
0/1/2. Match additional noise to the positive high-frequency-floor difference; never
subtract existing Kepler noise. Record actual coverage and duty, including any extra
loss from Kepler gaps. The resulting 396 cells reuse correlated source realizations.
Actual TESS sectors are analyzed individually under PP-06. The fixed Stage 3 feasibility
thresholds are reference-conditioned diagnostics, not blind detections or confirmations.
The native 1500-2700-microHz sidebands, 1800-2500-microHz envelope search and primary
Lightkurve reference values reproduce the exact Stage 3 feasibility policy. Additional
reduced-spectrum topology diagnostics use a separate recorded continuum and do not
change the native-policy classification.

Spectral audit: 4 preprocessing x 3 background families x 4 normalizations = 48 rows;
plus two background scales, two smoothing widths and two frequency resolutions
for each preprocessing branch = 24 more. Report all 72 rows and any claim narrowing.
Placement against Stage 4 design coordinates is domain context, not inverse calibration.

## T10.9/T10.10 and G10

Build and seal eight bounded claims and their evidence/control/limitation mappings
before rendering the manuscript. Draft introduction, methods, simulation context,
Rudy results, ablations, discussion and data/code availability. Supply ten SVG/PDF/PNG
figures under the unmodified `TA-PLOT-1.0` academic style. No delay figure is required
because the registered G7 action is drop. No external publication, repository upload
or DOI is manufactured. Supply editable LaTeX, checked bibliography and compiled PDF.

The freeze is an **internal review snapshot**. A fresh source copy/environment/process
must regenerate numeric tables, headline summaries and figures. This automated check
is distinct from independent human reproduction and claim review (D10.4). The signed
record must identify an independent reviewer and the exact freeze SHA256. G10 remains
`review_pending` until that record is valid. G9's pending proof review remains visible;
its new proposition is excluded from Paper I headline claims. Implementation completion
does not invent scientific approval or broaden the case study into a population result.
