# Stage 12 observed pilot results

These are descriptive results from the supplied archive. They do not complete scientific G12. All measurements below are traceable to `results/stage12/`.

## Population pilot

| Quantity | Baseline fractional MAE | Hybrid fractional MAE | Mean paired improvement | Conditional 95% paired CI | Practical margin |
|---|---:|---:|---:|---:|---:|
| numax | 0.024565 | 0.024452 | 0.000113 | [-0.000370, 0.000505] | 0.010 |
| dnu | 0.007679 | 0.008066 | -0.000388 | [-0.001313, 0.000603] | 0.005 |

The usable population consists of nine of 39 development stars. Inner-fold residual rank support is insufficient for 90% OOF intervals, so coverage is unavailable. No conventional catastrophic failures occur among these nine usable stars; failure/alias-risk classifiers and their calibration/decision curves are explicitly withheld. Failed and missing upstream stars are not counted as successful observations or as absent oscillation signals.

## Actual TESS sectors

All 11 actual sectors were analyzed; 0 of 44 method/quantity candidates were accepted. Each sector supplies four rows (baseline/hybrid × nu_max/Delta_nu). Every actual candidate has a weak-envelope, alias-ambiguity and domain-shift reason. Candidate values are archived for diagnosis; they are not oscillation detections. TESS probabilities and Kepler-derived intervals are unavailable under mission shift.

Four registered adjacent groups were combined by exposure-weighted, incoherent PSD averaging. Their envelope ratios remain below the registered 1.5 screening threshold; the combination products are candidate diagnostics rather than calibrated detections.

## Degradation and scope

The raw pilot contains 192 measured cells, eight cumulative levels, three real sector masks, two source offsets, and four matched draws. Every cell retains its physical time/flux array and source/model hashes. Candidate error increases strongly with the added TESS noise. QC accepts no transfer measurements in this delivered model domain; this is distinct from whether a candidate happens to lie near a published center.

`transfer_contributions.csv` reports matched cumulative operator changes. These changes do not isolate causal effects because the trajectory carries prior operators and changes the relevant estimator/window. Repeated windows and draws all belong to one star and supply no population power. Actual-versus-degradation agreement is withheld for this pilot and its rejected candidates.

G12 remains `validation_pending`. No positive complementarity, calibrated detection, quantified population equivalence or population transfer claim is supported. Broader TESS expansion stops at the stated Rudy transfer limits. No recalibration was authorized or fitted. The final holdout remains unopened.

Sources: `cohort_ledger.csv`, `increment.json`, `probability_calibration.json`, `transfer_run.json`, `transfer_curves.csv`, `transfer_contributions.csv`, `actual_tess.json`, and `actual_vs_degraded.json`.
