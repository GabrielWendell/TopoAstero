# D0.3 - Preregistered analysis protocol

**Protocol ID:** TAP-1.0  
**Frozen:** 2026-09-18  
**Scope:** method development, simulation calibration, Rudy benchmark, Kepler confirmation, and
bounded Kepler-to-TESS transfer

The machine-readable hypotheses in `registries/hypotheses.yaml` are authoritative. This document
fixes how evidence may be generated and labeled.

## Inferential ladder and partitions

| Role | Allowed use | Prohibited use |
| --- | --- | --- |
| Analytic | Exact identities, counterexamples, implementation tests | Population performance claim |
| Simulation pilot | Choose factors/ranges; debug estimators and null generators | Final operating-domain estimate |
| Simulation confirmation | Bias, coverage, Type-I error, power after pilot freeze | Retuning after confirmed result |
| Rudy descriptive benchmark | End-to-end transparency, localization, failure discovery | Population generalization claim |
| Development stars | Representation and hyperparameter selection | Final reported confirmation score |
| Internal validation stars | Bounded model/margin choice before lock | Repeated tuning without a change record |
| Final holdout stars | One unattended confirmatory execution | Any tuning, threshold choice, or exclusion invention |
| TESS transfer | Prespecified domain-shift and detectability test | Retrofitting the Kepler claim |

All measurements, quarters, and sectors of a star share one partition. A TESS observation of a star
cannot validate a method tuned on that star's Kepler data. Actual star assignments are created in
T2.8 after identity/QC resolution; the target final holdout fraction is approximately 20%, with
stratification frozen before labels are viewed. Rudy is always a descriptive benchmark, never a
final population holdout member.

## Primary hypotheses and metrics

| ID | Primary estimand | Primary metric | Strong baseline | Confirmatory interpretation |
| --- | --- | --- | --- | --- |
| H1 | Bias of topological `nu_max` and envelope strength | Paired absolute relative error; 68/95% coverage | pySYD/Lightkurve/background fit | Improvement, calibrated noninferiority with robustness/QC value, or bounded failure |
| H2 | Error of `Delta nu` from ridge-coherence maximizer | Paired relative error plus half/double-alias rate | ACF, PSPS, conventional echelle | Correct-spacing recovery without smoothing/graph domination |
| H3 | Error of one locked small-separation ratio | Paired absolute error and normalized-residual coverage | Peak-bagged/conventional frequency fit | At least one ratio recovered with calibrated uncertainty in adequate-S/N domain |
| H4 | Phase-sensitive excess of delay persistence | Maximum-statistic surrogate effect and conditional predictive gain | PSD-only features | Observed statistic differs from PSD-preserving surrogates after multiplicity control |
| H5 | Conditional gain from adding locked topology features | Paired out-of-sample log score; target-specific error/calibration secondary | Same model and folds with classical features only | Gain exceeds locked practical margin, or useful QC calibration improves |
| H6 | Validity and tightness of stability-to-physics bound | Empirical coverage and bound/observed-change ratio | Direct perturbation Monte Carlo | Bound is valid and changes at least one realistic observing/preprocessing decision |

The form and direction of these metrics are frozen. Numerical practical-equivalence margins require
scale estimates and are therefore scheduled, before holdout, in
`registries/pilot_decisions.yaml`. No unregistered metric can replace a failed primary metric.

## Exclusions and missing data

Exclusions are applied without viewing a topological score and must use one of these reasons:

1. unresolved or duplicate star/product identity;
2. corrupt file or checksum change;
3. nonfinite/physically invalid uncertainty or unit inconsistency;
4. cadence/time-order/overlap defect that cannot be repaired reproducibly;
5. insufficient valid coverage under a threshold frozen in the observation-model pilot;
6. target outside the declared solar-like main-sequence/early-subgiant population; or
7. unavailable required classical label for the stated comparison.

Every exclusion remains in the ledger with stage, reason, evidence, and whether the exclusion was
known before topology was computed. Missing values are never silently imputed. The imputation rule,
if needed, is selected on development data and rerun inside every resampling fold.

## Null families

1. Harvey-like background plus photon noise through the real sampling window.
2. Randomized mode comb/frequency labels at matched density and support.
3. Fourier phase randomization preserving the periodogram.
4. IAAFT preserving the marginal distribution and approximate PSD.
5. Injected known p-mode patterns in quiet/background segments.
6. Mission-window controls and correct-spacing versus half/double-spacing aliases.

The null is claim-specific. When scanning trial spacing or frequency bands, each surrogate records
the maximum statistic over the identical search; otherwise an explicitly registered FDR family is
used. Report empirical p-values, effect sizes, and detection probability, not p-values alone.

## Mandatory ablations and controls

- Peak prominence/merge tree versus PSD H0 persistence.
- Autocorrelation and PSPS versus topological `Delta nu` candidates.
- Topology-free periodic ridge/contrast score versus cylindrical persistence.
- Circular statistics versus persistence on mode-frequency clouds.
- PSD-only versus delay-topology features.
- Classical-only, topology-only, hybrid, and shuffled-topology models on identical star folds.
- Correct spacing versus half/double aliases and randomized labels.
- Registered preprocessing/background branches, including no-smoothing where meaningful.

An ablation that matches the full method is a retained scientific result and removes the stronger
novelty claim.

## Uncertainty and selection

Realization uncertainty uses block bootstrap or posterior predictive draws; measurement/model
uncertainty propagates background and mode-frequency draws; pipeline uncertainty spans registered
preprocessing branches. Every draw reruns feature construction, candidate selection, and failure
logic. Conditioning on a previously selected ridge is not a valid uncertainty interval.

Population validation uses repeated nested five-fold cross-validation grouped by star, subject to
feasibility after the Stage 2 inventory. Paired bootstrap intervals compare methods on the same
stars. Subgroup claims require a minimum size frozen from simulation/power analysis before holdout.

## One-time holdout policy

Before access, all of the following must be true:

- code tag, locked environment, data manifest, split file, and output schema are frozen;
- exclusions, missing-data rules, metrics, multiplicity, uncertainty, hyperparameters, thresholds,
  practical margins, and failure-return behavior are frozen;
- the unattended workflow passes on a structurally identical synthetic mock holdout;
- the principal researcher requests access and the supervisor plus data steward authorize it;
- a reproduction reviewer is assigned; and
- the analysis and deviation logs are ready.

The access event is appended once to `registries/holdout_access_log.csv` with manifest/split/code
hashes. The automated workflow runs without inspection between stars. Outputs are opened only after
completion and integrity checks. Post-access changes are deviations; a correctness fix requires a
complete rerun and is not a fresh confirmation.

## Decision outcomes

- **Advance:** mandatory criteria pass; inputs/configuration freeze.
- **Pass with limitation:** correctness and calibration pass, but the claim domain narrows.
- **Bounded repeat:** a named repairable defect, fixed scope, unchanged holdout, and deadline.
- **Stop/reframe:** redundancy, instability, invalid null, infeasibility, or failed interpretation.

The minimum publishable result is not universal outperformance. It is a mathematically explicit,
null-calibrated statement of stable complementary value, reliable QC, exact equivalence, or a
well-defined failure boundary.

## Deviations

Every departure records the affected hypothesis and estimand, rationale, inspection state, leakage
risk, action, approver, and whether the result remains exploratory or confirmatory. Negative and
invalid results are never deleted; invalid runs are excluded from inference with the defect stated.

