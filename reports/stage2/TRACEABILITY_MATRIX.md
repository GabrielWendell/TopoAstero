# Stage 2 traceability matrix

| Task | Implementation | Executable acceptance evidence |
| --- | --- | --- |
| T2.1 Resolve identities | `rudy_aliases.yaml`; stable KIC grouping with TIC, HD, Kepler, Gaia, 2MASS, TYC aliases and ICRS cross-match | exact ID/coordinate checks in `stage2_validation.py` |
| T2.2 Inventory Kepler | 10 payload-verified Rudy products; 2,159-candidate/66-star LEGACY MAST index; query scripts | counts, quarters, unique keys, metadata seals, acquisition-state tests |
| T2.3 Inventory TESS | 33 verified SPOC/TESS-SPOC/QLP products in 11 sectors | sector/author/cadence counts, FITS/QC metadata, SHA-256 fields |
| T2.4 Light-curve model | `light_curve.schema.json`, `LightCurveRow`, verified Q2 example | units, finite values, uncertainty, mission/cadence, monotonicity, JSON round-trip tests |
| T2.5 Spectrum model | `spectrum.schema.json`, `SpectrumRow`, PSD example | normalization, unit, Nyquist, window, background, provenance tests |
| T2.6 Reference data | 42 modes, 38 ratios, 264 stellar/global rows plus source/output manifests | row counts, source rows, hashes, versions, uncertainty checks |
| T2.7 Integrity checks | QC protocol, JSON/Markdown reports, header-only exclusion ledger | 11 passing checks for duplicates, time, gaps, NaNs, uncertainty, overlaps, units, checksums |
| T2.8 Population partitions | 39/13/13 star-grouped roles plus Rudy benchmark; policy, generator, balance report, SHA-256 seal | no-overlap, exact counts, Rudy-role, source/content seal, empty access-log tests |

## Deliverables

| Deliverable | Principal artifacts |
| --- | --- |
| D2.1 Rudy Kepler/TESS manifest and alias table | `data/manifests/stage2/rudy_*`, `mast_query_snapshot.json` |
| D2.2 Canonical light-curve, spectrum, mode, and stellar schemas | `schemas/*`, `data_model.py`, examples and reference tables |
| D2.3 QC report and exclusion ledger | `reports/stage2/qc_report.json`, `QC_REPORT.md`, `registries/exclusion_ledger.csv` |
| D2.4 Frozen star-grouped split | `population_partitions.csv`, `split_attestation.json`, `partition_balance.json` |

Every artifact included in the gate is size- and SHA-256-indexed by
`reports/stage2/deliverable_manifest.csv`. CI runs Stage 0, Stage 1, and Stage 2 contracts so this
stage cannot pass by regressing an earlier one.
