# Stage 3 traceability matrix

| Task | Evidence | Automated acceptance |
| --- | --- | --- |
| T3.1 Lightkurve case | exact products, one-command workflow, notebook, baseline table | displayed tutorial values reproduced within frozen tolerances |
| T3.2 independent pipeline | `classical.py`, comparison table/report | common conventions; distinct estimator; finite reconciled outputs |
| T3.3 background | H0/H1/H2 table and figure | exponential likelihood finite; H2 minimum BIC; analytic/injection tests |
| T3.4 window | six-row atlas and figure | Q2/Q5/Q6/Q7 plus absolute/compressed combination; duty/resolution/aliases |
| T3.5 echelle | three-trial table and SVG suite | orientation/order/smoothing/circular boundary frozen |
| T3.6 modes | 42-row audit and overlay | unique `(n,l)` source rows; all matches within frozen window; offsets explicit |
| T3.7 branches | branch registry and sensitivity table | all fields frozen; `classical_predeclared_no_topology`; no topology selection |
| T3.8 uncertainty | component table | 500 seeded resamples; random/pipeline/reference columns; quadrature check |
| T3.9 TESS | 11-sector table, note, figure | each sector separate; one marginal/ten failures; no combined detection |

| Deliverable | Files |
| --- | --- |
| D3.1 | workflow, acquisition adapter, configuration, notebook |
| D3.2 | baseline, comparison, uncertainty, run manifest |
| D3.3 | sensitivity report, background table, window atlas, branch registry |
| D3.4 | echelle/mode tables and five classical diagnostic SVGs |
| D3.5 | TESS note, sector table, feasibility SVG |
| G3 | acceptance JSON, validator, schemas, unit/integration/governance tests, CI gate |
