# Stage 0 report - Governance and reproducibility foundation

## 1. Scope and version

- **Stage:** S0, tasks T0.1-T0.8
- **Repository/distribution:** TopoAstero 0.1.0
- **Implementation date:** 2026-09-18
- **Reference environment:** Python 3.12.14, Linux x86_64, 9 logical CPUs, locked by
  `uv.lock`
- **Responsible role:** Principal researcher (Gabriel Wendell)
- **Input specification:** Detailed Agenda Chapter 2, pages 11-12; supporting proposal and Gantt
  snapshots are preserved with SHA-256 in `docs/source_documents/`
- **Data manifest:** `TA-DATASETS-1.0`; no mission payloads acquired and no final holdout opened

## 2. Questions and acceptance requirements

The stage must freeze hypotheses and terminology, establish repository/governance conventions,
preregister the validation and one-time holdout logic, plan data management, control risks, inventory
resources, and provide D0.1-D0.4. Gate G0 additionally requires a new collaborator to install and
run a smoke workflow and identify every planned dataset and primary hypothesis without oral
instructions.

The exact task-to-evidence mapping is `TRACEABILITY_MATRIX.md`.

## 3. Methods executed

1. Translated proposal H1-H6 into positive and null hypotheses, estimands, units, primary metrics,
   strong baselines, nulls, falsification rules, minimum publishable conclusions, and decision stages.
2. Cross-walked all RQ0-RQ9 and O1-O10; treated O1/O10 explicitly as operational scientific
   controls rather than artificial statistical hypotheses.
3. Defined fixed scientific language and prohibited shortcuts for persistence, ridges, coherence,
   topological echelle, detection, calibration, robustness, complementarity, and failure.
4. Implemented an installable Python package, canonical configuration hashing, provenance capture,
   exact one-dimensional H0 persistence, deterministic simulation, SVG/table/report generation,
   resource auditing, and Stage 0 contract validation.
5. Registered eight planned dataset families, eleven bounded pilot decisions, sixteen principal
   risks, the star-grouped split algorithm, and empty append-only holdout/deviation/change ledgers.
6. Added locked dependencies, clean-environment/container instructions, CI, issue/PR governance,
   schemas, notebook policy, figure recipe, source-document checksums, and a package build.

## 4. Results

### Governance and scientific controls

- Primary hypotheses: 6/6 present.
- Research questions: RQ0-RQ9 present.
- Objectives: O1-O10 present.
- Required frozen terms: 9/9 present, plus six supporting terms.
- Planned dataset families: 8/8 present with identity state, resolution stage, rights, and retention.
- Pilot decisions: 11, each with stage, owner, and required non-holdout evidence.
- Risks: 16, each with P/I, trigger, mitigation, owner, fallback, and review date.
- Final holdout: no assignments and zero access-log rows.

### Deterministic smoke workflow

- Experiment: `TA-S00-T08-SMOKE-R001`
- Configuration SHA-256: `571952aa0113f5f84c6f3ff2f791082f9befff1cdada5e0b3a5bf84b2ea54f72`
- Signal: 512 seeded samples.
- Result: 60 finite H0 bars and one essential class.
- Largest finite persistence: `2.401656179925063`.
- Stable result SHA-256: `91141ba6148cf9766db1be710533577db158a21e70dc92f4a0763a9c92cba847`.
- Output: signal/pair CSV tables, stable JSON summary, SVG figure, and full run manifest.

### Resource audit

- The 512-sample exact H0 benchmark completed 100 repetitions at approximately 0.6 ms/run in the
  audited runtime; this is a software-path check, not a large-grid forecast.
- Current 9-CPU/21-GiB/approximately 28-GB-free environment is adequate for S0 and bounded pilots,
  not the full 50,000-100,000 CPU-hour and 2-5-TB publication plan.
- MESA and GYRE were not detected. They are optional, gated S13 capabilities.
- The public MAST portal was independently reachable, but the package-runtime HTTPS probe returned
  `URLError`; programmatic access must be rechecked in the S2 acquisition environment.

## 5. Validation

| Check | Result |
| --- | --- |
| Locked install | PASS (`uv sync --locked --group dev`) |
| Lint | PASS (`ruff check .`) |
| Strict typing | PASS (`mypy src`) |
| Tests | PASS, 24/24 |
| Coverage | PASS, 88.31% (threshold 85%) |
| Governance contract | PASS |
| Stable smoke comparison | PASS; fresh output `summary.json` byte-matched reference |
| Package build | PASS; wheel and source distribution |
| Clean extracted-copy reproduction | PASS; fresh environment, smoke, comparison, lint, typing, tests, contract, build |

## 6. Negative results, limitations, and defects

- **Runtime archive probe:** did not verify MAST connectivity from this execution environment. The
  failure is preserved, with a T2 retry action; no local-cache workaround was treated as verified.
- **Full compute allocation:** not yet assigned. Scaling remains prohibited until S4 profiling and
  an institutional allocation/storage target are recorded.
- **MESA/GYRE:** absent and not required for the thesis core. Use is conditional on the extension
  gate and one-review-cycle cost bound.
- **Exact mission products and population split:** intentionally absent at S0. Creating them before
  T2 identity/QC work would violate the registered design.
- No scientific hypothesis was tested by the diagnostic smoke calculation.

No unresolved software defect blocks S1.

## 7. Deliverable register

The content-addressed file index is `deliverable_manifest.csv`.

| Deliverable | Status | Principal evidence |
| --- | --- | --- |
| D0.1 Project charter | Accepted | Scope, claims, roles, rhythm, change control |
| D0.2 Reproducibility specification | Accepted | Lock, seed/hash/manifest/test/archive contract |
| D0.3 Preregistered protocol | Accepted | Partitions, metrics, exclusions, nulls, ablations, holdout |
| D0.4 Running repository | Accepted | Install, CI, smoke, tests, build, clean reproduction |

## 8. Gate recommendation

**G0: PASS WITH REGISTERED LIMITATIONS.**

Every G0 clause is satisfied by the clean extracted-copy reproduction and the searchable machine
registries. The limitations concern external acquisition/HPC capability, not missing Stage 0
implementation. They are assigned to T2/S4 and do not authorize hidden manual steps or claim changes.

## 9. Downstream consequences

- S1 is technically ready and may begin after the charter's formal supervisor gate signoff.
- S2 must resolve exact KIC/TIC/HD/Gaia aliases, MAST product IDs/checksums, archive-runtime access,
  canonical schemas, and the star-grouped split before any population analysis.
- S3-S9 must close the scheduled pilot decisions before locked confirmation.
- The final holdout remains unopened; the current access log must stay empty until the signed
  pre-holdout checklist is complete.
