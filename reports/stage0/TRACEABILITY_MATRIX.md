# Stage 0 traceability matrix

The controlling specification is Chapter 2, pages 11-12 of the detailed agenda. Status reflects
the repository contract; external resource limitations are recorded rather than hidden.

| Requirement | Implementation evidence | Automated evidence | Status |
| --- | --- | --- | --- |
| T0.1 Freeze research questions | `registries/hypotheses.yaml`; `objective_crosswalk.yaml`; `docs/science/HYPOTHESIS_REGISTRY.md` | Exact H1-H6, O1-O10, RQ0-RQ9 checks | Complete |
| T0.2 Define terminology | `registries/terminology.yaml`; terminology/data dictionary | Required fixed-term and field tests | Complete |
| T0.3 Establish repository | `pyproject.toml`, `uv.lock`, `configs/`, `src/`, `tests/`, `workflows/`, `notebooks/`, `results/recipes/`, `environment/` | lint, strict types, tests, build, smoke, CI | Complete |
| T0.4 Establish governance | charter, governance policy, labels, issue/PR templates, ledgers | Stage-contract and CSV-state tests | Complete |
| T0.5 Preregister validation | protocol, split policy, empty one-time access log, pilot decisions, deviation/exclusion ledgers | holdout-unopened and decision-field tests | Complete |
| T0.6 Plan data management | DMP, raw/derived/archive tiers, planned inventory, example, JSON Schema, checksum CLI, DOI targets | dataset/schema completeness tests | Complete |
| T0.7 Build risk register | `registries/risk_register.yaml`; human review table | field/owner/date/count tests | Complete |
| T0.8 Inventory resources | resource note, machine audit, archive-access record, small persistence benchmark | audit JSON and resource tests | Complete with recorded external limits |

## Deliverables

| Deliverable | Primary path | Acceptance evidence |
| --- | --- | --- |
| D0.1 Project charter | `docs/governance/PROJECT_CHARTER.md` | scope, claims, priorities, roles, rhythm, and change control all explicit |
| D0.2 Reproducibility specification | `docs/reproducibility/REPRODUCIBILITY_SPECIFICATION.md` | lock, seed policy, manifest schema, hashes, tiers, archive plan, clean commands |
| D0.3 Preregistered analysis protocol | `docs/protocols/PREREGISTERED_ANALYSIS_PROTOCOL.md` | partitions, metrics, exclusions, ablations, nulls, uncertainty, one-time holdout |
| D0.4 Running repository skeleton | repository root | locked install, lint/type/test, smoke, CI, build, and reference outputs |

## Gate G0 clauses

| Clause | Evidence |
| --- | --- |
| Collaborator can create environment | README + `uv.lock` + container/conda bridge |
| Collaborator can run smoke without oral instructions | one documented CLI command and reference result hash |
| Every planned dataset identifiable | eight records in `planned_datasets.yaml`, including provisional identity status and resolution stage |
| Every primary hypothesis identifiable | H1-H6 registry and human view |
| Conclusion-changing open choices controlled | eleven scheduled pilot decisions with stage, owner, and evidence |
| No hidden final-holdout inspection | no assignments and empty access log, both tested |

The Stage 0 stage report supplies command outputs, test counts, checksums, limitations, and gate
recommendation.

