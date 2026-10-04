# Stage 11 population protocol (TA-S11-LEGACY-v1)

This is the executable analysis contract for T11.1-T11.11 (agenda PDF pages
33-34, printed pages 25-26). It extends the Stage 10 method snapshot without
changing byte-sealed Stage 0-10 source, science outputs or reference tables.
The additive CLI is `python -m topoastero.population_cli`, also exposed through
`workflows/run_stage11_legacy.py`. No new dependency or environment lock is needed.

## Cohort, reference edition and grouping

The original split contains 39 development stars, 13 internal validation stars,
13 final holdout stars, and Rudy (KIC 10963065), a descriptive benchmark only.
All products of a star inherit its role; months/quarters never increase the
population sample size. Splits are not recomputed using observed performance.
The original split SHA-256 is checked before every cohort/batch operation.

Global seismic/atmospheric references remain the checked Stage 2 Silva Aguirre
et al. (2017) tables. Their asymmetric uncertainty semantics are preserved.
Individual modes and frequency ratios use the corrected Lund et al. erratum
(ApJ 850, 110; DOI 10.3847/1538-4357/aa9658) distributed by CDS J/ApJ/835/172.
The reference manifest records URLs, byte hashes, row numbers and edition.
The CDS mode table repeats 45 numerically identical rows for KIC 3456181; they
are retained once with a duplicate-resolution ledger. Conflicting duplicates
stop import. This is metadata reconciliation, before observational topology.
No covariance matrix is available in the included reference bundle.

Exclusions live in `registries/stage11_exclusions.csv`, with reason, evidence,
owner/time and `topology_seen=false`. No stars are excluded in the delivered
implementation. Missing payloads are not exclusions and remain in catalogs.
Magnitude and median published radial-mode linewidth are available covariates;
individual evolutionary states are marked unclassified, without inventing labels.

## Observation operator and baseline

Every nonoverlapping Kepler monthly short-cadence FITS product follows PP-01:
default quality mask, finite PDCSAP flux, per-month normalization. Native LS PSDs
in ppm^2/uHz are rebinned to the common registered physical grid without
extrapolation. The primary spectrum is the retained-exposure-weighted monthly
mean. Retained cadence counts, full-span duration, spectral window and mask
duty cycle are archived. Duplicate timestamps between products stop the star.

This deliberately defines a population mean-spectrum estimator. It is not the
coherent full-span Rudy periodogram from Paper I. All point estimates and monthly
bootstrap intervals refer to the same population observation operator.
No missing flux is interpolated across gaps. Rebinning can interpolate source
ordinates inside their observed range when needed; it adds no independent data.

Background H0/H1/H2 fits use log residuals of frequency-bin means, not the raw
exponential-ordinate median/ln(2) convention. Fixed H2 is primary; all fitted
branches are retained. BIC/model probabilities are withheld for averaged PSDs.
A data-only envelope locates the excluded oscillation band. Published nu_max,
Delta nu or frequencies never determine the baseline search or background fit.

## Frozen topology and prior limitations

Normalized log(P/B) path-superlevel H0 supplies localized peaks. A weighted
peak centroid estimates nu_max inside the data-selected envelope. Independent
prominence matching checks the exact H0/prominence identity. A comb scan uses
registered nominal, half and double trial families around the classical data
spacing. Nominal selection is fixed; stronger aliases and boundary winners
produce flags, not star-specific adjustments. This is topology-enhanced
processing with shared classical anchors, not an independent likelihood model.

Cylinder fields use Stage 8's registered 24 phase bins, periodic boundaries,
fixed ridge graph and combined geometry/H0 score. Inference remains
`geometry_only`; no calibrated cylindrical spacing interval, degree identity,
mode lifetime or blind r02 is issued. Delay PH remains dropped at G7.
Ridge ratio checks are a separate reference-conditioned diagnostic: published
degrees and orders anchor nearby observed PSD peaks, a peak cannot be reused,
and missing modes remain missing. Formula checks compare ratios of published
median frequencies to published median ratios; these need not agree identically.
No claim of new blind topological ratio inference follows from this audit.

## Uncertainty, primary metrics and operating domain

Nonoverlapping months are resampled jointly for both estimators, weighted by
retained exposure. Backgrounds are refitted in every draw. Percentile intervals
have registered 90% level and conditional sampling scope. Any failed draw
withholds the interval and records `uncertainty_unavailable`; no selective
discarding of failed draws or variance addition is allowed.

Primary endpoints: nu_max and Delta nu. Paired bias, MAE, RMSE, fractional error,
catastrophic errors and 95% population bootstrap intervals use a common set of
successful stars. All attempted/valid/missing/limited/not-detected counts are
reported per method beside paired summaries. Population bootstrap samples stars
jointly across methods. Fewer than three stars withhold population intervals.
Reference-center coverage, Wilson intervals and reference-interval overlap are
reported separately. False confidence means a conditional interval missing the
published reference center; it is not error against a known true stellar value.

Practical equivalence is paired TOST on topology-minus-classical absolute
fractional-loss differences. Margins: 0.01 (nu_max), 0.005 (Delta nu). Alpha: 0.05.
The paired t approximation is disclosed. Holm correction includes both registered
endpoints; an unavailable endpoint counts as p=1 in the family. Failure to find
superiority is not equivalence. No subgroup significance claims are tested.

LEGACY contains selected oscillators. Specificity, null false-alarm rate,
AUROC/AUPRC and probability calibration/Brier score cannot be established with
positive-only observations. Envelope-ratio thresholds are heuristic quality
rules, not calibrated detection probabilities. These quantities are withheld
rather than assigning artificial negatives to missing observations.

Fixed observational/stellar bins cover nu_max, Delta nu, temperature, magnitude,
envelope ratio, duty cycle, duration and linewidth, plus published mode category
and unclassified evolutionary state. Missing covariates form an explicit group.
Sparse groups report counts and descriptive failure intervals; performance
claims are suppressed below three valid stars. No unsupported partial pooling.

## Development QA, signed release and one-time confirmation

Development/internal runs are checksum-sealed and resumable. `log-change`
records general code/configuration fixes and affected roles before confirmation;
rerun affected roles in a new output directory. Individual stellar tuning is
not part of this implementation. Freeze requires complete acquired inputs,
current development/internal results and no unresolved pipeline failures.

Freeze records supervisor and data-steward authorization supplied by the
operator, the actual built container image digest, source/configuration hashes,
locked environment, products/references, exclusions, thresholds, metrics and
analysis rules. An external RSA/ECDSA private PEM key signs the exact canonical
payload through OpenSSL; the public key/signature are archived. This is an
actual verifiable signature, not an automated reviewer attestation. Protect the
private key and retain the approved public-key fingerprint separately.

`open-confirmation` checks all release seals, signature and holdout payload
hashes before atomically reserving the one-time state. It processes all holdout
stars automatically, preserves completed checkpoints including scientific
failures, and seals the first complete archive. A completed run cannot reopen.
An interrupted run can resume only unchanged code/configuration/inputs; completed
stars are reused, never re-fit. A process lease prevents concurrent resumes.
After an OS crash, a stale lease may be removed only with a documented incident;
do not delete the opening state or completed checkpoints.

Public star identifiers and literature metadata are visible. Local guards and
signatures do not prevent deliberate copying/deletion of a repository or access
outside this program. Supervisor/steward review of signed releases and access
logs supplies the procedural boundary; cryptographic identity blinding is not
claimed. Confirmation never updates models, thresholds, exclusions or QA logs.

## Gate and release scope

`validate_stage11.py` checks implementation, evidence hashes and honest status.
`--require-confirmation` additionally requires a completed valid frozen holdout.
The delivered project reports `population_pending`, not scientific G11 passed:
only Rudy payloads were supplied. `pass_with_limitation` is available after
completed confirmation, with the fixed scope above. Paper II is a generated
working manuscript; publication readiness requires scientific review.
G9 proof review and G10 human independent reproduction remain pending exactly
as in the supplied snapshot. No review, submission, DOI or holdout access is
fabricated. All Stage 0-10 validators must continue to pass unchanged.
