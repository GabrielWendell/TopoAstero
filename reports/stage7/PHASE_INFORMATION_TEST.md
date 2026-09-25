# Stage 7 PSD-preserving phase-information test

Each original trace was compared with 24 phase-randomized and 24 IAAFT surrogates. The per-cell
statistic was the maximum normalized dominant `H1` persistence across all four registered delay
rules, and plus-one p-values were followed by BH at `q=0.10` on the untouched evaluation cells.

- Phase-randomized evaluation BH rejection rate: **0.000**.
- IAAFT evaluation BH rejection rate: **0.000**.
- Maximum phase-randomized Fourier-amplitude error: **2.640e-16**.
- Maximum median IAAFT Fourier-amplitude error: **0.008**.

The maximum statistic covers delay selection within each signal. Non-rejections and empty/weak
loops remain serialized; no favorable cells were selected after outcome inspection.
