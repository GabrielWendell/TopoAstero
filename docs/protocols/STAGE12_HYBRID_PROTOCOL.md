# Stage 12 hybrid inference protocol

This protocol implements T12.1-T12.11 without claiming that passing software tests completes scientific G12. The uploaded Stage 11 archive contains nine usable development stars, one usable internal-validation star, and an unopened final holdout. Counts are generated from the active Stage 11 evidence manifest. The raw population cache is external to the supplied ZIP; only Rudy's 10 Kepler and 11 TESS products are included locally.

## Task and feature lock

`registries/stage12_tasks.csv` and `stage12_features.csv` define the tasks, labels, operational utility and small feature blocks. Inputs never include published stellar labels, literature linewidths, individual degree/order assignments, reference-conditioned ridge ratios or cohort identifier encodings. Published nu_max/Delta_nu centers are supervised outcomes only. The baseline includes conventional global estimates, envelope ratio, observation span/duty/resolution, the exact prominence-centroid control and graph geometry. The hybrid adds three locked score descriptors. Path H0 adds no independent information beyond prominence. Cylinder results remain geometry-only; delay PH remains dropped.

Regression predicts log corrections to conventional estimates using standardized ridge regression. The quality tasks predict catastrophic conventional-estimator failure and nominal-alias unreliability when both outcomes have support. Astrophysical signal-presence detection is withheld because LEGACY is selected to contain oscillators. Transfer recoverability is a separate positive-signal parameter/QC task, never signal-presence specificity.

## Star grouping, tuning and intervals

Training uses development stars only. Rudy, internal-validation stars and final holdout stars cannot enter training. Three deterministic outer folds and three inner folds are assigned by SHA-256 of seed/star ID. All observations of a parent star remain together. Preprocessing and penalty selection occur inside training folds; each parent has total fitting weight one. The locked penalty grid is 1, 10, 100.

For each outer test star, interval radii use inner OOF absolute log residuals, aggregated conservatively once per star. The finite rank is ceil((n+1)*0.90). If that rank exceeds the number of independent calibration stars, the interval is unavailable. These are empirical OOF intervals, not exact split-conformal guarantees, individual-frequency posteriors or stellar posterior intervals. Coverage refers to a published reference center. Probability calibration uses inner OOF logits only; the outer outcomes never choose a calibration layer. Missing class/fold support withholds the probability rather than substituting a prior or zero.

## Increment and multiplicity

Paired improvement is baseline absolute fractional loss minus hybrid absolute fractional loss. Bias, MAE, RMSE, catastrophic counts and interval availability/coverage use the same successful star set; missing/failed stars remain in the overall cohort ledger. The primary practical margins are 0.01 for nu_max, 0.005 for Delta_nu and 0.01 for failure Brier. The superiority family includes all three primary tests; missing failure support has p=1. Regression uses three-test Holm; failure quality uses conservative three-test Bonferroni. Equivalence uses a separate two-regression TOST/Holm family. Alias reliability and subgroup diagnostics remain exploratory.

Paired bootstrap intervals resample stars, not segments or sectors. They condition on fitted OOF models and do not claim to integrate repeated model-selection uncertainty. At least 20 development stars are required before a confirmation release can be signed; this is a minimum support guard, not an asserted power calculation. Confirmation is the original 13-star holdout, with a separate minimum of 10 usable stars and the same registered metrics. Positive regression increment must exceed its practical margin with corrected significance and interval support. Failure prediction requires Brier improvement beyond its margin AND a positive lower bound on operational net-benefit improvement at the locked 0.25 threshold. Single-class confirmation cannot support failure calibration.

## Quality and mission shift

Hard reason codes and model probabilities are distinct. Low envelope/background ratio, competing aliases, unsupported windows, invalid inputs and missing models are recorded. Predictions outside standardized training support receive domain-shift flags. Corrections larger than a factor of two are withheld. Candidate estimates remain inspectable even when QC does not accept a measurement. TESS risk probabilities and Kepler empirical intervals are withheld because applying a Kepler model does not transfer their calibration. QC screening is not an oscillation detection; no false-alarm rate is inferred from the positive-only cohort.

## Physical degradation

The supplied raw experiment uses the fixed Rudy Q5 source, exposure integration by a piecewise-linear primitive, and all 11 registered real TESS cadence masks. Native/exposure controls use up to 60 days of supported Kepler source; the duration level uses the actual sector span. Noise, the real window, additional 75% duty retention and 30% contaminating-to-target flux are applied as explicit sensitivity steps. A final short-duration trajectory uses 13.7 days. Exposure/target cadence may never be shorter than the source cadence, and no long source gap is interpolated across.

The white-floor nuisance is measured on the integrated Q5 native high-frequency PSD with the registered median/log(2) approximation. Existing Kepler noise is retained. Added Gaussian noise matches a positive floor difference under the existing Stage 10 PSD convention. Source noise decomposition, stationary noise and passband response remain assumptions. A unit color response is a sensitivity, not a measured Kepler/TESS color conversion. TESS PDCSAP can already correct crowding, so added contamination is not presented as a required correction.

Seeds are determined by parent star, sector, source offset and draw; paired models share a dataset and degradation levels use common random sequences. The pilot uses sectors 14/40/81, offsets 0/30 days and four draws. The full preset uses all 11 sectors and 32 draws, with the same fixed feature/quality design. Every physical degraded time/flux array and completed analysis failure is archived. Resume reuses exact completed checkpoints; changed code, models, configuration or payload hashes are rejected.

## Actual sectors and comparisons

Models/configuration are hashed before actual-sector processing, and checked throughout. These sectors were already examined in Stage 10; this is a frozen-method descriptive case study, not a new blinded test set. Adjacent registered groups 14+15, 40+41, 74+75 and 80+81+82 are averaged as exposure-weighted PSDs. No phase stitching across years is used. Combination scores remain candidate diagnostics; missing detections and pipeline failures are retained.

The actual-versus-degradation comparison uses the noise+real-window level, matching sector duration; extra duty and contamination are separate sensitivity analyses. With at least 32 accepted simulated estimates, an accepted actual candidate can be compared to conditional 5%-95% draw quantiles. These quantiles do not establish calibrated population prediction coverage. Pilot support, rejected candidates and missing sectors produce explicit withholding. All sectors/draws still describe ONE parent star. Broader TESS scope remains stopped pending a prospective powered multi-star plan and independent actual targets.

## Release, confirmation and recalibration

Freeze Stage 12 models before the Stage 11 holdout is opened. The signed release records actual supervisor/steward identities, a real container image digest, exact code, models, training data, features, tasks, metrics and protocol. A release created after any Stage 11 opening is rejected. Stage 12 never opens raw holdout data itself. It applies signed models once to Stage 11's first completed, validated archive; local exclusive state protects against repeated scoring. An interrupted Stage 12 confirmation remains auditable and cannot be casually rerun or deleted to obtain a new score. Procedural guards are not cryptographic blinding of public star identities.

Recalibration is disabled by default. An explicit authorization string is required to fit the prespecified star-weighted median log-offset layer on DEVELOPMENT simulations from at least 10 non-Rudy parent stars. Final/internal holdout data, Rudy and actual sectors are forbidden as fitting sources. The layer changes no features. It must be evaluated on disjoint simulation stars, included in a new frozen release, and cannot alter already signed/opened results. Application does not automatically restore TESS probability/interval calibration.

Scientific complementarity, quantified equivalence and transfer scope are separate decisions. No software gate, synthetic test fixture or repeated single-star segment can supply missing population evidence. Paper III is generated from evidence, with current limitations and negative results visible.

The optional log-offset layer applies only to TESS-like transfer predictions. It never changes native Kepler predictions or the primary Kepler LEGACY confirmation archive. A TESS calibration requires disjoint transfer-simulation validation; successful Kepler confirmation is not evidence that this transfer calibration works.
