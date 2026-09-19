# Rudy benchmark specification

## Identity and role

Rudy is **KIC 10963065**, also recorded as HD 176693, Kepler-408, and TIC 48450369. The benchmark
is transparent development and regression evidence. It is not the population-level final holdout.
The machine identity is `evidence/benchmarks/rudy_identity.yaml`.

## Authoritative seismic targets

| Quantity | Published value | Source and role |
| --- | ---: | --- |
| `numax` | `2203.7 -6.3/+6.7 uHz` | LEGACY Paper II Table 3; authoritative global target |
| `dnu` | `103.179 -0.027/+0.027 uHz` | LEGACY Paper II Table 3; authoritative global target |
| individual modes | 42 rows over published `(n,l)` labels | LEGACY Paper I machine-readable Table 6; authoritative frequency targets |
| `Teff` | `6140 +/- 77 K` | LEGACY Paper II Table 3; atmospheric input |
| `[Fe/H]` | `-0.19 +/- 0.10 dex` | LEGACY Paper II Table 3; atmospheric input |

The 42-row file preserves asymmetric frequency errors and optional amplitude, linewidth, and Bayes
factor fields exactly as represented in the publisher table. Empty optional fields stay empty.

## Context-only values

The official Lightkurve first-look tutorial uses quarters Q2, Q5, Q6, and Q7 and reports:

| Quantity | Value |
| --- | ---: |
| `numax` | `2145 uHz` |
| `dnu` | `103.11 uHz` |
| mass | `1.08 Msun` |
| radius | `1.23 Rsun` |
| `logg` | `4.29 dex(cgs)` |

It reports no uncertainties and explicitly presents a first-look workflow [@LightkurveTutorial].
These rows are marked `context_only`; they test workflow reproduction but cannot replace the full
LEGACY values.

Paper II also publishes a stellar-properties flat file. The retrieved file does not identify which
of the seven modelling pipelines produced its rows. The Rudy mass, radius, `logg`, age, luminosity,
density, and distance are preserved for reconciliation but marked `context_only` until that
attribution is resolved. No seven-pipeline consensus is invented.

## Acceptance use in later stages

- Global estimators: report bias/error relative to the authoritative Table 3 value and whether the
  interval overlaps its published bounds.
- Mode recovery: match only with a preregistered one-to-one rule using `(n,l)` and frequency
  tolerance; do not tune tolerance on the final holdout.
- Missing returns remain failures rather than being dropped.
- Lightkurve reproduction: explain expected differences caused by quarter span, preprocessing,
  periodogram, and estimator versions.
- TESS products and exact MAST identifiers remain a Stage 2 acquisition task.

The long-form numerical authority is `evidence/benchmarks/benchmark_targets.csv`.

