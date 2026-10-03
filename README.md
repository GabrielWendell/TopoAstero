# TopoAstero

TopoAstero is the reproducible research repository for the project *Topological
Asteroseismology of Solar-like Stars*. The repository name and Python distribution are
`TopoAstero`; the import package and command-line program are `topoastero`.

Version 0.11.0 implements Stages 0-10 through the Rudy/Paper I internal review freeze. It contains
traceable derived tables, payload-verified mission manifests, a reproduced Lightkurve Rudy case, an
independent classical pipeline, exact analytic regressions, a stochastic oscillator laboratory,
calibrated null/coverage maps, a localized dependency-light TDA core, a locked compact statistic
set, exact PSD peak/saddle localization, uncertainty-bearing `nu_max` and comb APIs, reason-coded
quality control, and source-backed figure suites, but redistributes no Kepler, TESS, or publisher
payloads.

## Reproduce Stages 0-10

Install [uv](https://docs.astral.sh/uv/) and run from the repository root:

```bash
uv sync --locked --group dev
uv run topoastero smoke --config configs/smoke.yaml --output-dir results/smoke
uv run topoastero audit-resources --root . --output reports/stage0/resource_audit.json
uv run topoastero validate-stage0 --root .
uv run topoastero validate-stage1 --root .
uv run topoastero validate-stage2 --root .
uv run topoastero validate-stage3 --root .
uv run topoastero validate-stage4 --root .
uv run topoastero validate-stage5 --root .
uv run topoastero validate-stage6 --root .
uv run topoastero validate-stage7 --root .
uv run topoastero validate-stage8 --root .
uv run topoastero validate-stage9 --root .
uv run ruff check .
uv run mypy src
uv run pytest
uv build
```

The smoke command constructs a seeded two-mode signal, computes exact zero-dimensional
superlevel persistence on a path, and writes a table, persistence pairs, an SVG figure, a stable
result hash, and a run manifest. The workflow does not need mission data or a network connection.
Stage 1 validation is also offline: it checks literature/source links, the 66-star LEGACY sheet,
276 numerical target rows, 42 Rudy mode frequencies, novelty-search semantics, bibliography
integrity, deliverable hashes, G1, and the complete Stage 0 regression contract.
Stage 2 validation stays offline as well: it checks stable aliases, 43 payload-verified Rudy
products, 2,159 inventory-only LEGACY candidates, four canonical row types, 344 reference rows,
QC, the sealed 66-star grouped split, deliverable hashes, G2, and all earlier contracts.
Stage 3 validation checks both Rudy pipelines, PSD/background/window conventions, six frozen
preprocessing branches, three conventional echelle trials, all 42 mode overlays, component-separated
uncertainty, 11 individual TESS sectors, source/output hashes, the `TA-PLOT-1.0` publication-style
and figure-provenance contract, G3, and all earlier contracts.
Stage 4 validation checks 12 exact analytic cases, stochastic PSD/time-domain recovery, the
balanced 72-cell pilot, payload-derived mission windows, seven independently evaluated null
families, max-statistic multiplicity control, 27 uncertainty-coverage cells, the compute/precision
budget, the locked confirmation protocol, G4, and all earlier contracts.
Stage 5 validation checks the exact path/Rips/periodic-grid core, six backend cross-checks, all five
candidate representations on the same 72-cell panel, physical localization, five independent null
calibrations, nine nuisance audits, redundancy/ablation evidence, the locked retained set, G5, and
all earlier contracts.
Stage 6 validation checks four normalized-spectrum contracts, exact localized PSD `H0`, independent
prominence equivalence, three paired `nu_max` methods, explicit half/nominal/double comb candidates,
ACF/PSPS ablations, nuisance-matched maximum-statistic nulls, six robustness branches, five
reason-coded flags, G6, and all earlier contracts.
Stage 7 validation checks four simulation-only delay rules, missing-aware unreduced embeddings,
`H0/H1` plus limited `H2`, metric and landmark convergence, paired phase-randomized/IAAFT maximum
statistics, classical coherence controls, held-out lifetime ablations, rolling stability, the
locked retain/drop decision, G7, and all earlier contracts.
Stage 8 validation checks the exact periodic cubical seam, the matched fast/full `H0` reduction,
15-spacing half/nominal/double alias search, maximum-statistic background nulls, paired six-method
benchmark, stochastic/background intervals, identified-mode ratio audit, failure atlas, the
geometry-only G8 decision, and all earlier contracts.
Stage 9 validation checks proof-linked analytic and numerical identities, fixed-mask diagram
stability, conditional finite-order ridge jumps, Gamma tail calibration, nine counterexamples,
explicit stellar systematics, source-backed figures, an executed notebook and byte provenance.
It reports implementation **PASS** separately from scientific G9 **review_pending**: a named
independent proof review is required to accept the new proposition. Stage 8 remains geometry-only.

To regenerate the Stage 9 evidence in a clean checkout before the validator, run:

```bash
uv run python workflows/run_stage9_mathematics.py
uv run python workflows/execute_stage9_notebook.py
uv run python workflows/build_stage9_manifest.py
uv run topoastero validate-stage9 --root .
```

To reacquire the exact 10 Kepler and 11 SPOC TESS payloads into an external cache and regenerate the
full Stage 3 tables and figures:

```bash
uv run --extra astronomy python workflows/run_stage3_classical.py \
  --cache-dir /absolute/path/to/topoastero-cache --download
```

## Stage 0 implementation map

| Task | Frozen artifact | Executable evidence |
| --- | --- | --- |
| T0.1 Research questions | `registries/hypotheses.yaml`, `registries/objective_crosswalk.yaml` | Governance tests require H1-H6, O1-O10, and RQ0-RQ9 |
| T0.2 Terminology | `registries/terminology.yaml`, science dictionary | Required-term tests |
| T0.3 Repository | Package, configs, tests, workflows, notebooks, manifests, reports, figure recipe, `uv.lock` | CI, smoke workflow, build |
| T0.4 Governance | Project charter, governance policy, issue/PR templates, ledgers | Stage contract tests |
| T0.5 Validation | Preregistered protocol, split policy, holdout log, pilot-decision schedule | Empty-holdout and protocol tests |
| T0.6 Data management | DMP, dataset inventory, schemas, checksum tooling | Manifest validation tests |
| T0.7 Risks | Machine-readable and human-readable risk registers | Required-field tests |
| T0.8 Resources | Resource note, audit command, persistence benchmark | Generated audit JSON |

The detailed file-level mapping is in
[`reports/stage0/TRACEABILITY_MATRIX.md`](reports/stage0/TRACEABILITY_MATRIX.md).

## Stage 1 implementation map

| Task | Frozen artifact | Executable evidence |
| --- | --- | --- |
| T1.1 Physics map | physics matrix and solar-like physics note | required concepts, limitations, and source links |
| T1.2 Classical pipelines | eight-baseline matrix and pipeline note | exact CB-01..CB-08 plus H1-H6 crosswalk |
| T1.3 Rudy evidence | identity YAML, target table, 42-mode table | aliases, exact global targets, mode count and numeric bounds |
| T1.4 LEGACY population | 66-star population sheet and specification | unique KICs and four authoritative targets per star |
| T1.5 Mathematical TDA | nine-topic theorem matrix and assumptions map | exact TDA-01..TDA-09 with explicit non-claims |
| T1.6 Astronomy TDA | adjacency/gap map | direct/adjacent distinction and transfer limits |
| T1.7 Novelty audit | dated 18-query execution log and gap memo | failed queries cannot count as zero; two complete services |
| T1.8 References | clean BibTeX, claim audit, schemas, quarterly protocol | key equality, DOI uniqueness, full source resolution |

The detailed mapping and gate record are in
[`reports/stage1/TRACEABILITY_MATRIX.md`](reports/stage1/TRACEABILITY_MATRIX.md) and
[`reports/stage1/G1_ACCEPTANCE.json`](reports/stage1/G1_ACCEPTANCE.json).

## Stage 2 implementation map

| Task | Frozen artifact | Executable evidence |
| --- | --- | --- |
| T2.1 Identity | Rudy alias/coordinate record | exact KIC/TIC/Gaia/HD and cross-match checks |
| T2.2 Kepler | 10 verified Rudy products and 66-star candidate index | product uniqueness, query, metadata and payload-state checks |
| T2.3 TESS | 33 SPOC/TESS-SPOC/QLP products in 11 sectors | sector, author, cadence, FITS metadata, checksum checks |
| T2.4 Light curves | closed schema, dataclass, verified excerpt | unit, uncertainty, cadence, monotonicity and round-trip tests |
| T2.5 Spectra | normalization/window/background schema and dataclass | Nyquist, PSD convention, provenance tests |
| T2.6 References | modes, ratios, and stellar/global tables | cardinality, uncertainty, version and row-lineage checks |
| T2.7 QC | 11-check report and exclusion protocol | duplicates, gaps, NaNs, time, overlap, unit and checksum checks |
| T2.8 Split | 39/13/13 grouped split plus Rudy benchmark and SHA-256 seal | no-star-overlap, role-count, source/content-seal tests |

The detailed mapping and gate record are in
[`reports/stage2/TRACEABILITY_MATRIX.md`](reports/stage2/TRACEABILITY_MATRIX.md) and
[`reports/stage2/G2_ACCEPTANCE.json`](reports/stage2/G2_ACCEPTANCE.json).

## Stage 3 implementation map

| Task | Frozen artifact | Executable evidence |
| --- | --- | --- |
| T3.1 Lightkurve case | exact Q2/Q5/Q6/Q7 workflow and executed notebook | tutorial `numax`, `dnu`, mass, radius, and log g reproduced |
| T3.2 Independent pipeline | Harvey-whitened envelope and FFT-ACF implementation | shared-unit/convention comparison and joint-uncertainty audit |
| T3.3 Background | H0/H1/H2 likelihood/AIC/BIC table | H2 selection plus analytic/injection tests |
| T3.4 Window | per-quarter and combined atlas | duty cycle, resolution, aliases, absolute/compressed comparison |
| T3.5 Echelle | three conventional trial spacings | fixed orientation, smoothing, orders, and circular phase edge |
| T3.6 Modes | 42-row published-mode audit | residuals and explicit publisher/echelle order offsets |
| T3.7 Branches | six-branch preprocessing registry | four executed Kepler sensitivities; no topology-based choice |
| T3.8 Uncertainty | 500-resample component table | random, pipeline-choice, reference, and joint terms separated |
| T3.9 TESS | 11 single-sector SPOC pilot | one marginal candidate, ten non-detections, no forced combination |

All Stage 3 and later figures use the project-wide visual contract in
[`src/topoastero/style.py`](src/topoastero/style.py); usage, accessibility, and provenance rules are
documented in
[`docs/reproducibility/PLOTTING_STYLE_GUIDE.md`](docs/reproducibility/PLOTTING_STYLE_GUIDE.md).

The detailed mapping and gate record are in
[`reports/stage3/TRACEABILITY_MATRIX.md`](reports/stage3/TRACEABILITY_MATRIX.md) and
[`reports/stage3/G3_ACCEPTANCE.json`](reports/stage3/G3_ACCEPTANCE.json).

## Stage 4 implementation map

| Task | Frozen artifact | Executable evidence |
| --- | --- | --- |
| T4.1 Exact cases | analytic derivation and 12-case registry | path-persistence, delay-ellipse, comb-alias, peak-profile, and ridge tests |
| T4.2 Simulator | damped-mode/background/observation API | seeded frequency- and time-domain tests |
| T4.3 Validation | 256-spectrum ensemble and mode recovery | PSD moments, variance, frequency, intrinsic height, and linewidth gates |
| T4.4 Factorial pilot | balanced 72-cell immutable matrix | complete pilot output spanning every registered factor level |
| T4.5 Nulls | seven nuisance-matched generators | white/red/background/comb/phase/IAAFT/real-window calibration |
| T4.6 Multiplicity | max-statistic, empirical-p, and BH-FDR utilities | 32-statistic family scope; pointwise thresholds diagnostic-only |
| T4.7 Uncertainty | 27 split calibration/evaluation cells | separate realization/pipeline terms and 0.9125-0.971875 coverage |
| T4.8 Compute | 12 runtime/memory measurements | MCSE-derived 256 null and 320 coverage repetitions |
| T4.9 Confirmation | locked protocol version 1.0 | prespecified endpoints, margins, stopping, and holdout rules |

The detailed mapping and gate record are in
[`reports/stage4/TRACEABILITY_MATRIX.md`](reports/stage4/TRACEABILITY_MATRIX.md) and
[`reports/stage4/G4_ACCEPTANCE.json`](reports/stage4/G4_ACCEPTANCE.json).

## Stage 5 implementation map

| Task | Frozen artifact | Executable evidence |
| --- | --- | --- |
| T5.1 Filtrations | representation specification and parameter registry | five complete domain/direction/normalization contracts |
| T5.2 Backends | `topoastero.tda` and representation adapters | exact path, Rips, periodic grid, distances and summaries |
| T5.3 Cross-checks | six-case backend table | prominence, MST, exact-square, cylinder/disk and metric tests |
| T5.4 Localization | localized pair API and JSON catalog | time, frequency, landmark, mode and pixel mappings |
| T5.5 Summaries | 13-candidate feature registry | four retained physical statistics; no feature bank |
| T5.6 Nuisances | nine-perturbation table | affine, monotone, sampling, embedding, smoothing, grid and boundary tests |
| T5.7 Redundancy | rank/MI matrix and six-fold ablations | topology-free conditional comparisons on development simulations |
| T5.8 Selection | locked selection registry and memo | PSD/delay/echelle proceed; LC diagnostic; mode cloud dropped |

The detailed mapping and gate record are in
[`reports/stage5/TRACEABILITY_MATRIX.md`](reports/stage5/TRACEABILITY_MATRIX.md) and
[`reports/stage5/G5_ACCEPTANCE.json`](reports/stage5/G5_ACCEPTANCE.json).

## Stage 6 implementation map

| Task | Frozen artifact | Executable evidence |
| --- | --- | --- |
| T6.1 Normalization | spectrum contract and four-method registry | primary `log(P/B)` plus ratio, residual, and uncertainty-aware audits |
| T6.2 Exact `H0` | localized peak API and pair schema | endpoint births, one essential class, birth and merge-saddle frequencies |
| T6.3 Prominence | independent elder-rule path scan | analytic/realistic equality table and equivalence-limited claim |
| T6.4 `nu_max` | centroid/median/Huber API with intervals | paired smoothing and explicitly labeled pySYD-style controls |
| T6.5 Comb | persistence difference/autocorrelation scores | half/nominal/double candidates plus ACF and PSPS controls |
| T6.6 Significance | nuisance-matched maximum-statistic nulls | independent FPR and false-confidence evaluation |
| T6.7 Robustness | six-branch recomputation atlas | diagram distance, estimator shift, and comb-winner changes |
| T6.8 Quality | five-code locked QC registry | reliable, limited, and not-detected rows retained in full |

The detailed mapping and gate record are in
[`reports/stage6/TRACEABILITY_MATRIX.md`](reports/stage6/TRACEABILITY_MATRIX.md) and
[`reports/stage6/G6_ACCEPTANCE.json`](reports/stage6/G6_ACCEPTANCE.json).

## Stage 7 implementation map

| Task | Frozen artifact | Executable evidence |
| --- | --- | --- |
| T7.1 Delay selection | four-rule simulation-only policy | per-cell lag/H1 audit and method summary |
| T7.2 Embeddings | missing-aware robust sliding-window API | complete-window and deterministic density-control audit |
| T7.3 Persistence | unreduced VR `H0/H1` and limited `H2` | localized diagram suite and metric/landmark convergence |
| T7.4 Coherence | physical-target response surfaces | amplitude, linewidth, lifetime, quality-factor, and mixture map |
| T7.5 Phase nulls | paired phase-randomized and IAAFT maxima | plus-one p-values, PSD audit, and evaluation-only BH map |
| T7.6 Controls | seven classical coherence/Fourier controls | held-out topology/classical/combined lifetime ablation |
| T7.7 Segmentation | quarter/half/full rolling analysis | finite-realization intervals, bottleneck stability, vineyard track |
| T7.8 Decision | locked dual-path retain/drop policy | G7 calibrated-negative decision and critical-path action |

The detailed mapping and gate record are in
[`reports/stage7/TRACEABILITY_MATRIX.md`](reports/stage7/TRACEABILITY_MATRIX.md) and
[`reports/stage7/G7_ACCEPTANCE.json`](reports/stage7/G7_ACCEPTANCE.json).

## Stage 8 implementation map

| Task | Frozen artifact | Executable evidence |
| --- | --- | --- |
| T8.1 Mathematical object | normalized log(P/B) field on order × circle | missing-order-aware cubical/F2 API and formal science note |
| T8.2 Boundary | periodic seam, radial nonwrap | exact cylinder/rectangle and fast/full regression tests |
| T8.3 Ridge paths | circular maxima and connected graph | up to three competing adjacent-order hypotheses |
| T8.4 Score | finite H0 plus graph, orderwise diagnostic | frozen formula and topology-free ablation |
| T8.5 Aliases/null | Stage 6-anchored 15-point grid | half/nominal/double scores, independent null maxima and p-values |
| T8.6 Uncertainty | stochastic/bootstrap and background branches | 90% spacing and circular ridge-location intervals |
| T8.7 Small separation | anchored ridge angles and identified modes | r02 proxy, five-point ratios, published formula audit |
| T8.8 Failures | six prespecified perturbations | diagnostic stress/failure atlas |
| T8.9 Comparison | same trials and simulations for six methods | conventional, Hough, graph, ACF/PSPS and topology |
| T8.10 Figure | TA-PLOT-1.0 paired echelle | same spectrum, cylinder ridges, phase uncertainty overlay |

The bounded negative utility decision is recorded in
[`reports/stage8/G8_ACCEPTANCE.json`](reports/stage8/G8_ACCEPTANCE.json): geometry passes,
but topological correct-alias accuracy is 0.20 versus graph-only 0.60 and declared 90% interval
coverage is 0.20 on the five prespecified eligible evaluation cells. The combined score is not
a validated population estimator. See
[`reports/stage8/TRACEABILITY_MATRIX.md`](reports/stage8/TRACEABILITY_MATRIX.md).

## Stage 9 implementation map

| Task | Artifact | Executable evidence |
| --- | --- | --- |
| T9.1 | Definitions, fixed-mask/F2 boundary and stochastic assumptions | closed protocol and formal chapter |
| T9.2 | Peak identity, sinusoid ellipse and lifted ratio propositions | independent seeded/property regressions |
| T9.3 | Fixed-complex stability and new conditional target-ridge bound | diagram bottleneck and finite-order jump tests |
| T9.4 | Raw-Gamma Chernoff/union calibration | 4096 seeded draws and Wilson interval |
| T9.5 | Explicit seismic/stellar log budgets | separate correction arguments and exact interval tests |
| T9.6 | Nine assumption-breaking constructions | catalog and machine-readable adversarial examples |
| T9.7 | Theorem/proposition/approximation/empirical claim register | IDs S9-P1–P6, S9-T1, S9-E1, S9-C1 |
| T9.8 | Review packet and clean-extraction recipe | executed notebook, CI, manifests; **independent review pending** |

The [formal chapter](docs/science/STAGE9_THEOREMS_AND_PROOFS.md),
[traceability matrix](reports/stage9/TRACEABILITY_MATRIX.md) and
[G9 record](reports/stage9/G9_ACCEPTANCE.json) distinguish automated implementation
integrity from the human proof-review requirement. The proposition concerns a specified,
observed target candidate in consecutive trial rows; it does not establish a global score
bound or reverse Stage 8's negative utility verdict.

## Stage 10 implementation map

All T10.1-T10.10 have an executable implementation and a mapped evidence artifact.
See [task traceability](reports/stage10/TRACEABILITY_MATRIX.md) and the
[reproduction protocol](docs/reproducibility/STAGE10_REPRODUCTION.md).

```text
uv sync --locked --group dev --extra astronomy
uv run python workflows/reproduce_stage10.py --cache-dir ../topoastero-mission-cache --download
uv run python workflows/reproduce_stage10.py --cache-dir ../topoastero-mission-cache --clean-check
uv run topoastero validate-stage10 --root .
uv run python workflows/replay_stage10_reduced.py
```

The first workflow verifies all 21 frozen public products, regenerates 72 registered
spectral diagnostics, 256 conditional window-matched nulls, quarter/monthly/stochastic
uncertainty, 396 Kepler-to-TESS cells, ten academic figure sets, the claim ledger and
the complete editable/compiled Paper I draft. TeX is required to compile the PDF;
the analysis/figures use the locked astronomy extra. The clean check uses a fresh
source copy, locked environment and new process. Offline reduced replay is separate.

The [Paper I draft](paper1/main.pdf) is an **internal review freeze**. Stage 7's delay
drop and Stage 8's geometry-only verdict are preserved. Cylindrical ratios and
population claims are withheld. G9 proof review and G10 independent human
reproduction/claim review remain pending; automated tests do not fill those records.
No submission, archive DOI or public deposition has been performed.

## Repository layout

```text
TopoAstero/
|- configs/                 Frozen workflow configurations
|- data/                    Raw, derived, archive tiers and immutable manifests
|- docs/                    Charter, governance, protocol, DMP, science definitions
|- evidence/                Stage 1 literature, benchmark, search, and reference records
|- environment/             Container and cross-platform environment specifications
|- notebooks/               Readable demonstrations only; never the sole analysis path
|- registries/              Hypotheses, decisions, risks, splits, experiments, changes
|- reports/stage0..stage9/  Acceptance evidence and machine audit outputs
|- results/                 Machine-readable outputs and figure recipes
|- schemas/                 JSON Schemas for configuration and provenance records
|- src/topoastero/          Installable Python package
|- tests/                   Unit, integration, analytic, and governance tests
`- workflows/               Thin, unattended workflow entry points
```

## Scientific guardrails

- Every topological statistic has a topology-free control and an appropriate null.
- All observations from one star stay in one partition.
- Rudy (KIC 10963065) is a transparent benchmark, not the population-level final holdout.
- Hyperparameters, thresholds, metrics, and failure-return behavior are frozen before final
  holdout access.
- Negative results, failed representations, aliases, and deviations remain in the ledgers.
- Figures derive from machine-readable tables and immutable configurations.

The scientific definitions and acceptance logic are normative in the registries. Prose files
explain those records but do not silently override them.

## Current boundaries

- LEGACY archive candidates are metadata-inventoried but cannot become inputs until their payload
  SHA-256 values are computed; only the 43 Rudy products are payload-verified at G2.
- Five recent QLP products do not provide a per-cadence uncertainty column; the missing state is
  explicit. The Stage 3 feasibility pilot therefore uses the homogeneous SPOC two-minute family.
- TESS sectors remain individual at G3: one marginal candidate and ten non-detections do not
  justify a forced combined detection.
- Lightkurve's ACF2D result has no native uncertainty. The registered segment bootstrap is labeled
  separately, and the independent `numax` remains materially background/estimator sensitive.
- The portable repository has no independent secret store, so split identities are cleartext and
  auditable. The holdout remains unopened for topological analysis under the access-log policy.
- The Stage 1 novelty result is a dated search conclusion, not proof that no uncatalogued direct
  precedent exists; its next scheduled update is 2026-12-19.
- LEGACY is a selected high-signal population. Population-wide performance claims require broader
  samples and the Stage 2 stratification plan.
- The TESS sector list in the planned inventory is proposal-stage information and must be
  re-queried before use.
- MESA/GYRE is an extension capability. The core Stage 0 workflow is CPU-only and independent
  of either installation.
- Practical-equivalence margins that require empirical scale information are registered as
  bounded pilot decisions, with stage and owner, rather than selected after viewing holdout data.
- Stage 4 calibrates compact folded-spectrum/H0 summaries; it does not yet establish a population-
  level advantage over classical estimators. That question remains behind the locked confirmation
  and holdout rules.
- Stage 5 uses simulation-development data only. Its delay statistic is exploratory, its PSD
  statistics entered the Stage 6 prominence/equivalence audit, and its echelle ridge lifetime still
  requires the Stage 8 graph-only/alias tests; G5 is not an astrophysical performance claim.
- Stage 6 finds exact finite path-`H0`/prominence equivalence and therefore retains persistence only
  as an organization/localization layer for this representation. The offline pySYD-style comparator
  is not an external pySYD execution; genuine pySYD output is required before a population claim.
- Stage 6 uses locked simulations only. Its G6 result calibrates reliability and failure return; it
  does not substitute for the unopened Kepler population holdout.
- Stage 7 found no positive PSD-preserving phase or classical-adjusted predictive path, so delay
  persistence is dropped from the critical path in the tested regime.
- Stage 8 validates the periodic geometry but fails the frozen alias/coverage/increment utility
  gates. The score and angular proxy cannot be promoted to an astrophysical estimator without a
  new preregistered, independent evaluation. Published modes audit formulae only.
- Stage 9's new conditional ridge statement awaits independent human proof review. Its Gamma
  statement applies to unsmoothed raw bins under a specified marginal model; its stellar
  propagation requires independently supplied correction allowances. G9 is review pending.

## License and citation

Code is released under the BSD 3-Clause License. Data products retain the terms of their source;
project-authored documentation and tables are intended for CC BY 4.0 release at publication.
Use `CITATION.cff` for software citation. No DOI has been assigned through Stage 10.


## Stage 11 - Kepler LEGACY population validation

The additive Stage 11 commands preserve the Stage 10 source interface and the
original star-grouped partitions. Start with:

```text
uv run python workflows/validate_stage11.py --root .
uv run python workflows/replay_stage11_reduced.py --root .
```

Full acquisition/development, signed release and one-time confirmation commands
are in [the Stage 11 reproduction guide](docs/reproducibility/STAGE11_REPRODUCTION.md).
All T11.1-T11.11 implementations and current scientific completion states are
in [the traceability matrix](reports/stage11/TRACEABILITY_MATRIX.md). The delivered
scientific G11 is `population_pending`: 66-star metadata and corrected references
are included, while only Rudy observation payloads were supplied. No final holdout
was opened and no Paper II population performance claim is made.
