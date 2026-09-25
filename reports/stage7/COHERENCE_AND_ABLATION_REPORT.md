# Stage 7 coherence calibration and classical-control ablation

Dominant `H1`, total `H1`, and persistence entropy were related descriptively to simulated
amplitude, linewidth, lifetime, quality factor, and mode mixture. Confirmatory utility was assessed
by training on 12 calibration cells and evaluating on 12 untouched cells for the target
`log10(lifetime_days)`.

| Feature family | Evaluation MAE (dex) |
| --- | ---: |
| Topology | 0.5325 |
| Classical controls | 0.6324 |
| Combined | 0.7183 |

The frozen combined-versus-classical improvement is **-0.136**; the retain threshold is
`0.10`. Correlation p-values in the response table are descriptive and are not used as a gate.
