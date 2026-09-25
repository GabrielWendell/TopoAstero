# Stage 7 delay-topology protocol

Protocol ID: `TA-STAGE7-DELAY-1.0`  
Run ID: `TA-S07-DELAY-R001`  
Status: locked before execution  
Data boundary: simulations only; population data and the final holdout are prohibited.

## Confirmatory sequence

1. Select the first 24 balanced Stage 4 simulation cells without inspecting Stage 7 outcomes.
2. Assign odd-numbered cells to calibration and even-numbered cells to evaluation.
3. Compare all four delay rules, retaining multiscale consensus as the frozen primary method.
4. Build robust, complete-window embeddings and compute unreduced VR persistence in
   \(H_0/H_1\), with limited \(H_2\) and metric/subsampling audits.
5. Compute paired maximum-statistic phase-randomized and IAAFT tests using fixed delay trials.
6. Evaluate topological, classical, and combined lifetime predictors on the untouched evaluation
   cells.
7. Quantify quarter/window dependence and rolling-diagram uncertainty.
8. Apply the locked retain/drop rule without changing thresholds after evaluation.

## Failure handling

Every failed embedding, empty finite diagram, and non-rejection remains in the evidence tables.
No cell may be removed because its topology is weak. A negative result passes G7 when the null
tests, control ablation, stability analysis, and drop decision are complete and reproducible.

## Multiplicity and claim boundary

The per-cell maximum spans the four registered delays. Across evaluation cells, the reported
phase map uses BH at \(q=0.10\). Stage 7 supports only a simulation-regime claim; no result in this
stage is a population or final-holdout claim.

