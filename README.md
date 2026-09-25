# TopoAstero

TopoAstero is the reproducible research repository for the project *Topological
Asteroseismology of Solar-like Stars*. The repository name and Python distribution are
`TopoAstero`; the import package and command-line program are `topoastero`.

Version 0.7.0 implements Stages 0-6 through persistent topology of the power spectrum. It contains
traceable derived tables, payload-verified mission manifests, a reproduced Lightkurve Rudy case, an
independent classical pipeline, exact analytic regressions, a stochastic oscillator laboratory,
calibrated null/coverage maps, a localized dependency-light TDA core, a locked compact statistic
set, exact PSD peak/saddle localization, uncertainty-bearing `nu_max` and comb APIs, reason-coded
quality control, and source-backed figure suites, but redistributes no Kepler, TESS, or publisher
payloads.

## Reproduce Stages 0-6

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
|- reports/stage0..stage6/  Acceptance evidence and machine audit outputs
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

## License and citation

Code is released under the BSD 3-Clause License. Data products retain the terms of their source;
project-authored documentation and tables are intended for CC BY 4.0 release at publication.
Use `CITATION.cff` for software citation. No DOI has been assigned through Stage 6.
