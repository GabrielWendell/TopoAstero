# Astronomy TDA adjacency and gap map

The machine-readable gap map is `evidence/literature/astronomy_tda_gap_map.csv`.

## Evidence classes

| Class | Meaning in TopoAstero |
| --- | --- |
| Direct precedent | Same scientific task and substantially the same data representation. It must be incorporated and the novelty claim narrowed. |
| Adjacent application | Astronomy or Kepler use with a different target/estimand. It supports design choices only by analogy. |
| Mathematical adjacency | A representation or theorem tested outside the astronomical task. It establishes plausibility and assumptions. |
| Audited gap | No direct precedent found by the dated query set. It is not proof of global absence. |

Persistent homology has been used for cosmological map summaries [@Heydenreich2021], and a TDA
approach has been reported for an exoplanet-oriented Kepler light-curve task [@Chung2025]. Those
papers are relevant adjacent evidence. Neither validates persistent-homology estimators of
`numax`, `dnu`, solar-like mode frequencies, or an echelle-ridge score.

## Transfer rules

- Transfer a representation only with an ablation against a simpler representation.
- Transfer an inference procedure only after checking its independence/exchangeability conditions.
- Never transfer a performance number across data geometry or task.
- Treat generic periodic-signal results as mathematical motivation; stochastic multi-mode
  oscillations with gaps require dedicated simulation.
- Re-run the novelty audit quarterly and before manuscript submission. A discovered direct
  precedent triggers the novelty-redefinition rule in the research-gap memorandum.

