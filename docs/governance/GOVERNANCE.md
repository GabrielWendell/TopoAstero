# T0.4 - Repository and scientific governance

## Branch and review policy

`main` is the only release branch and should be protected on the remote. Direct pushes are limited
to emergency administrative repairs. Work branches use one of:

- `feature/Sxx-Txx-short-name`
- `fix/Sxx-Txx-short-name`
- `docs/Sxx-Txx-short-name`
- `experiment/Sxx-Hx-short-name`

Every pull request links a task or risk, states scientific impact, passes CI, and has at least one
reviewer other than its author. Changes to hypotheses, partitions, exclusions, primary metrics,
nulls, practical margins, failure returns, or holdout behavior require both the supervisor/PI role
and methods reviewer role. A documentation-only review cannot approve a changed estimator.

## Required checks

The protected branch requires:

1. formatting/lint (`ruff check`);
2. strict static typing (`mypy src`);
3. unit, integration, analytic-regression, and governance tests (`pytest`);
4. deterministic smoke workflow;
5. Stage 0 contract validation; and
6. package build.

Warnings that may change numerical meaning are failures. Flaky tests are defects, not acceptable
noise.

## Coding and analysis standard

- Python 3.11-3.13; `src/` layout; type hints on public and scientific functions.
- Small pure functions for scientific kernels; explicit units and coordinate conventions.
- No scientific logic exists only in a notebook.
- Configurations are immutable after use and addressed by canonical SHA-256.
- Floating-point tolerances have physical or numerical justification in the test.
- Public functions document mathematical object, assumptions, units, and failure behavior.
- Randomness is explicit and registered. Global implicit RNG state is prohibited.
- Tables precede figures; a figure recipe names its inputs, config, generator, and output.
- Raw data are immutable and never committed. Derived rows point to raw product IDs and hashes.
- Failed experiments remain in the ledger with factual results and a decision.

## Identifier conventions

- **Experiment:** `TA-Sss-Ttt-SLUG-Rrrr`, for example `TA-S00-T08-SMOKE-R001`.
- **Dataset:** `DS-SHORT-NAME`.
- **Risk:** `RISK-SCI-###`, `RISK-DATA-###`, `RISK-COMP-###`, or `RISK-PROG-###`.
- **Decision:** `DEC-Sss-###`.
- **Change request:** `CR-YYYY-NNN`.
- **Figure/table:** `FIG-Sss-SLUG-NNN` and `TAB-Sss-SLUG-NNN`.

IDs are immutable. A superseding record points to the old ID; it does not reuse it.

## Issue labels

The machine-readable label set is `.github/labels.yml`. Every issue has exactly one stage label,
one type label, and one priority. Scientific result states (`negative-result`, `blocked`,
`holdout-sensitive`) are additive. `holdout-sensitive` forbids screenshots, labels, or metrics from
protected confirmation data in the public issue.

## Decision authority

| Decision | Recommends | Approves | Evidence |
| --- | --- | --- | --- |
| Routine implementation | Contributor | Principal researcher | Tests and task acceptance |
| Representation retained/dropped | Principal researcher | Supervisor + methods reviewer | Null, ablation, localization, stability |
| Primary metric/margin freeze | Principal researcher | Supervisor + methods reviewer | Simulation/development pilot only |
| Dataset exclusion | Data steward | Principal researcher; supervisor if cohort changes | Predefined QC and exclusion ledger |
| Holdout opening | Principal researcher | Supervisor + data steward | Signed pre-holdout checklist |
| Release/gate passage | Principal researcher | Supervisor; reproduction reviewer can block | Stage report and independent rerun |
| Authorship dispute | Manuscript team | Supervisor/institutional process | CRediT record and journal policy |

## Review and authorship schedule

Authorship and contribution expectations are reviewed at Stage 0 close, at the charter of each
paper, after each major gate, when a contributor's role changes, and before submission. The project
uses CRediT statements. Data access, seniority, or supervision alone does not automatically fix
author order; journal and institutional rules govern the final decision.

## Holdout and deviations

The final LEGACY partition is star-grouped and opened once. No result from it may determine a
representation, hyperparameter, threshold, exclusion, practical-equivalence margin, or narrative
claim. The access event is appended to `registries/holdout_access_log.csv`. The log is empty at S0.

Deviations use `registries/deviation_log.csv` and state whether affected data had already been
inspected. Exploratory analyses are welcome when labeled exploratory; relabeling them as
confirmatory is prohibited.

## Releases and archive

Release candidates use signed or annotated Git tags when infrastructure permits, a locked
environment, manifests, checksums, test reports, a clean reproduction report, and a deliverable
index. Software releases target Zenodo DOI archival; data tables and figure inputs receive a
separate DOI when size or licensing makes that clearer.

