# LEGACY population specification

## Population

The Stage 1 population sheet contains all 66 Kepler Asteroseismic LEGACY stars published by Lund
et al. and Silva Aguirre et al. [@Lund2017; @SilvaAguirre2017]. The sample consists of high-signal
solar-like oscillators observed in short cadence for at least about 12 months and selected to avoid
obvious strongly bumped dipole-mode cases. It spans main-sequence stars and slightly evolved
subgiants; it is not a representative sample of all Kepler solar-like stars.

`evidence/benchmarks/legacy_population.csv` records one row per unique KIC with:

- exact KIC and Rudy alias where applicable;
- selection and evolutionary-scope statements;
- published `numax`, `dnu`, lower/upper intervals;
- `Teff`, `[Fe/H]`, their uncertainties, and atmospheric-reference code; and
- source key and table location.

## Target hierarchy

1. **Authoritative benchmark:** Paper II machine-readable Table 3 global and atmospheric values.
2. **Frequency reference:** Paper I machine-readable tables; Rudy's full 42-mode slice is checked
   in at Stage 1, and Stage 2 may ingest the population tables under immutable manifests.
3. **Context only:** tutorial values and any catalog row whose method attribution is incomplete.

The long-form target table has 264 authoritative rows: four quantities for each of 66 stars. It
also has five Lightkurve and seven Paper II Rudy context rows. Uncertainty bounds are non-negative
magnitudes and keep the published lower/upper orientation.

## Selection and split rules

- All observations of one KIC remain in one split.
- Rudy may be used during transparent development but its role must be stated.
- Population claims must report the high-SNR selection limitation and performance by at least
  signal-to-noise or magnitude proxy, temperature/evolution proxy, linewidth, and duration when
  those fields become available in Stage 2.
- Final-holdout membership remains governed by the Stage 0 split policy; this file neither assigns
  nor reveals it.

## Access and provenance

The publisher inputs are not redistributed. URLs, retrieval dates, and SHA-256 hashes are in
`evidence/benchmarks/source_provenance.csv`. To reproduce the checked-in tables, download and
verify those files and run:

```bash
uv run python workflows/build_stage1_benchmarks.py \
  --global-table apjaa5587t3_mrt.txt \
  --stellar-table apjaa5587t4_mrt.txt \
  --mode-table apjaa5593t6_mrt.txt
```

