# Inherited administrative repairs

The uploaded archive had stale Stage 9 software seals and a Stage 10 clean-reproduction record marked not_run. Original administrative inputs are retained in inherited_input_snapshot/. Earlier numerical tables, mathematical claims, core source files and star partitions were not edited.

The existing repair_portability.py workflow refreshed size/hash fields for the updated top-level documentation/CI and inherited Stage 9 records. A fresh locked Stage 10 raw-product run completed successfully, but the original strict comparison found optimizer differences (maximum relative difference approximately 1.34e-7) and SVG byte differences. That complete strict attempt is preserved in strict_stage10_reproduction_attempt.json.

The additive check_stage10_portable_reproduction.py workflow then ran a second fresh locked raw-product reproduction. It used declared rtol=1e-6 and atol=1e-6 numerical tolerances, exact identifiers/flags/row counts/manuscript source, exact SVG text/viewBox and bounded rendered-PNG pixel differences. All 46 scientific/figure/manuscript comparisons passed. Detailed per-file maxima and pixel metrics are in portable_stage10_reproduction_comparison.json.

The machine clean-reproduction record now records this actual portable verification. Independent human proof/reproduction review remains pending. The refreshed Stage 10 source/evidence manifest preserves the original scientific output bytes and adds the current extension source/admin evidence; it is not an external reviewer approval.
