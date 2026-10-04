# Stage 10 task/deliverable traceability

| Task | Implementation | Evidence |
|---|---|---|
| T10.1 | `configs/stage10_rudy.yaml`; public MAST acquisition; masks/cadence audit | `benchmark_capsule.json`; `sampling_audit.csv` |
| T10.2 | Lightkurve tutorial and independent Harvey/ACF; modes/scaling | `classical_branches.csv`; `background_models.json`; `broad_spectrum.csv`; `published_mode_overlay.csv`; `scaling_uncertainty.csv` |
| T10.3 | Exact localized path H0, prominence, comb and window-matched maxima | `localized_peaks.json`; `spectral_score_scan.csv`; `conditional_null_tests.csv`; `quality_flags.csv` |
| T10.4 | Periodic cylinder, competing graph/Hough/conventional controls | `cylinder.json`; `echelle_branch_controls.csv`; `echelle_score_scan.csv`; `echelle_bootstrap.csv`; `ratio_reference_audit.csv` |
| T10.5 | Conditional agenda clause: honor G7 drop | `summary.json`; prior `G7_ACCEPTANCE.json`; limitation/claim ledger |
| T10.6 | Quarter/cumulative, 256 monthly bootstraps, 64 stochastic repeats | `quarter_stability.csv`; `monthly_spectra.csv`; `monthly_bootstrap.csv`; `stochastic_draws.csv`; `uncertainty_budget.csv` |
| T10.7 | Cadence integration, duration/duty/noise, all actual windows | `kepler_to_tess.csv` (396 cells); `tess_sectors.csv` (11 sectors); `simulation_placement.csv` |
| T10.8 | All 48 factorial and 24 one-factor sensitivities | `robustness.csv` (72 rows); `echelle_branch_controls.csv` |
| T10.9 | Claims/controls/limitations frozen before draft | `claim_evidence.csv`; `claim_audit.json`; `LIMITATIONS_AND_NEGATIVE_RESULTS.md` |
| T10.10 | Complete internal review manuscript and 10 figure sets | `paper1/`; `figure_manifest.json`; `figures/` |

| Deliverable | Location | Completion |
|---|---|---|
| D10.1 | `results/stage10/` | Generated and sealed |
| D10.2 | `workflows/reproduce_stage10.py`; reproduction protocol | Public-ID one-command capsule |
| D10.3 | `paper1/main.tex` / `main.pdf`; ten styled PDF/SVG/PNG sets | Internal review freeze |
| D10.4 | `clean_reproduction.json`; claim audit; independent review record | Automated reproduction recorded separately; independent human review pending |
| G10 | `G10_ACCEPTANCE.json` | Implementation versus independent-review status explicitly separated |
