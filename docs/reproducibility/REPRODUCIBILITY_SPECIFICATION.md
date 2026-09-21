# D0.2 - Reproducibility specification

**Specification:** RS-1.1

**Updated:** 2026-09-20
**Normative machine records:** `pyproject.toml`, `uv.lock`, `schemas/`, `configs/`, and
`registries/`

## Environment contract

The authoritative Python environment is `pyproject.toml` plus `uv.lock`. A collaborator runs
`uv sync --locked --group dev`; `--locked` must fail rather than silently resolve a different
environment. Python 3.12 is the reference interpreter and 3.11-3.13 are supported in CI.

`environment/environment.yml` is a convenience bridge for conda users; it invokes the locked uv
installation and is not an independent dependency authority. `environment/Dockerfile` provides a
clean Linux build. Stage 3 adds locked NumPy/SciPy/Matplotlib numerical dependencies. Astropy and
Lightkurve are a locked `astronomy` extra used only for FITS acquisition and exact tutorial
reproduction; the offline contract and independent numerical core do not require that extra.

Every result manifest records package version, Git commit/dirty state when available, Python,
platform, CPU count, configuration hash, seeds, inputs, output checksums, and timing. A dirty tree
is allowed during exploration but not in a confirmation or release manifest.

## Seed policy

1. Every stochastic workflow has a decimal master seed in its immutable configuration.
2. Independent streams derive from `SHA256("TopoAstero|master|namespace|replicate")`; the first
   unsigned 64 bits are the child seed. The namespace describes the stochastic object, not the
   worker number.
3. Parallel scheduling never determines a seed. Retry uses the same seed unless the experiment ID
   changes.
4. Seed lists or the deterministic rule are stored in the experiment ledger and run manifest.
5. Random seeds support exact reruns but do not replace repeated-realization uncertainty.

The Stage 0 smoke and Stage 3 bootstrap master seed, `20260721`, is fixed from the planning-edition
date. Stage 3 records the namespace and 500 resamples in its manifest.

## Configuration hashing

YAML is parsed with a safe loader, converted to sorted compact JSON, encoded as UTF-8 ASCII escapes,
and hashed with SHA-256. This makes comments and key order irrelevant while making every semantic
value hash-relevant. Input payloads use byte-level SHA-256. Hash algorithm changes require a schema
version increment.

## Manifest contract

Each raw product receives a stable dataset ID plus provider, collection, mission identifiers,
product/observation ID, retrieval timestamp, immutable URI or query, size, SHA-256, license/terms,
and status. Derived products add parent checksums, configuration hash, code version, schema version,
and producing experiment ID. `schemas/data_manifest.schema.json` is normative.

Mutable local filenames are never identities. MAST files remain discoverable by archive IDs and
queries even when payloads are not redistributed.

## Test tiers

| Tier | Purpose | When required |
| --- | --- | --- |
| Unit | Pure functions, parsers, hashes, exact path persistence | Every change |
| Analytic regression | Sinusoid/comb/ridge identities and invariances | Every scientific-kernel change |
| Integration | Config -> computation -> tables/figure/manifest | Every change |
| Governance/schema | H1-H6, datasets, risks, terms, holdout state | Every change |
| Smoke | Small deterministic end-to-end workflow | Every pull request and release |
| Backend agreement | Independent TDA/spectral implementations | When a second backend enters |
| Clean environment | Locked install, all checks, artifact regeneration | Every gate and submission |

Coverage is a diagnostic; the 85% threshold does not substitute for analytic tests.

## Output and figure rules

Tables use explicit units, missing-value semantics, uncertainty definition, sample count, exclusions,
and quality flags. Figures name a machine-readable source table and immutable recipe. Numerical
claims are computed from tables, not recovered from graphics. A released figure is rebuilt in a
clean environment and its source table is archived.

Stage 3 and later figures must use `src/topoastero/style.py` visual contract `TA-PLOT-1.0` and
`save_figure`. Each SVG embeds the software/style versions and machine-readable source; each run
manifest records the style context, TeX choice, and primary format. Direct workflow-level
`rcParams` changes and `savefig` calls are rejected by the plotting-policy test. The normative
usage and accessibility rules are in `docs/reproducibility/PLOTTING_STYLE_GUIDE.md`.

## Archive plan

- Git remote: code, configurations, schemas, compact tables, recipes, and documentation.
- MAST: authoritative raw Kepler/TESS payloads referenced by IDs and checksums.
- Institutional storage: working raw/derived data with versioned snapshots.
- Zenodo target: tagged software release, lock, manifests, compact benchmark tables, and reports.
- Optional separate dataset DOI: larger publishable derived tables and figure inputs.

Raw public mission data need not be duplicated in the DOI deposit when a manifest and exact
regeneration command suffice. Expensive or fragile derived products are archived even when they can
in principle be regenerated.

## Reproduction levels

- **R0 audit:** all IDs, hashes, schemas, and commands are present.
- **R1 computational:** the same locked inputs reproduce tables within declared tolerances.
- **R2 independent:** a reviewer on a clean machine follows only repository instructions.
- **R3 scientific:** conclusions survive registered alternative preprocessing and uncertainty
  branches.

Gate G0 requires R2 for the data-free smoke workflow. Stage 3 supplies R2 through exact payload
hashes plus one command and R3 through frozen branch/uncertainty sensitivity. Later scientific
gates require R2 for their core workflow and R3 for headline conclusions.
## Cross-platform byte portability

Governed text artifacts use UTF-8 with LF line endings and repository-relative POSIX paths.
Generators must use `topoastero.portability`; CI enforces this with
`topoastero check-portability`. The repair procedure is documented in
`docs/reproducibility/CROSS_PLATFORM_PORTABILITY.md`.
