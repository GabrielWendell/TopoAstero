# TopoAstero

TopoAstero is the reproducible research repository for the project *Topological
Asteroseismology of Solar-like Stars*. The repository name and Python distribution are
`TopoAstero`; the import package and command-line program are `topoastero`.

Version 0.3.0 implements Stages 0-2 through the data acquisition, provenance, and canonical-model
gate. It contains traceable derived tables and payload-verified mission manifests but redistributes
no Kepler, TESS, or publisher payloads.

## Reproduce Stages 0-2

Install [uv](https://docs.astral.sh/uv/) and run from the repository root:

```bash
uv sync --locked --group dev
uv run topoastero smoke --config configs/smoke.yaml --output-dir results/smoke
uv run topoastero audit-resources --root . --output reports/stage0/resource_audit.json
uv run topoastero validate-stage0 --root .
uv run topoastero validate-stage1 --root .
uv run topoastero validate-stage2 --root .
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
|- reports/stage0..stage2/  Acceptance evidence and machine audit outputs
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
  explicit and the optional TESS transfer case remains nonblocking.
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

## License and citation

Code is released under the BSD 3-Clause License. Data products retain the terms of their source;
project-authored documentation and tables are intended for CC BY 4.0 release at publication.
Use `CITATION.cff` for software citation. No DOI has been assigned through Stage 1.
