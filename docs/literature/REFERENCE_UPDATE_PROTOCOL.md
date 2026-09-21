# Reference validation and quarterly update protocol

## Admission rule

Prefer the primary paper, publisher machine-readable table, theorem paper, or official software
documentation. A review may support physical synthesis but must not replace the primary catalog
for a numerical target. Add a record only after checking title, authors, year, venue, DOI/URL, and
the exact claim or equation it supports.

## Required records

Every admitted key appears exactly once in both:

- `evidence/references/topoastero_stage1.bib`; and
- `evidence/references/reference_audit.csv`.

The audit records primary-source status, DOI and URL, verification date and route, supported claim,
the equation/table checked, and caveats. Every `source_keys` cell in the evidence matrices must
resolve to one of these keys. DOI strings are lowercased for duplicate checks.

## Numerical target rule

Every number in `benchmark_targets.csv` carries an object ID, quantity, value, unit, uncertainty
status, method, source key, source location, reconciliation note, and benchmark/context status.
Blank uncertainties mean “not reported”; they are never interpreted as zero. Rounding, data-span,
or method differences are retained as separate rows rather than averaged.

## Quarterly cycle

1. Re-run the novelty queries and record both successes and failures.
2. Review new direct and adjacent candidates from title/abstract; inspect the primary full text for
   any candidate that could alter a claim.
3. Resolve DOI metadata at the publisher or registration agency; check for duplicate normalized
   DOI and duplicate title/year pairs.
4. Add claim-level support and a limitation to the appropriate evidence matrix.
5. If a benchmark table has changed upstream, preserve the old checksum and add the new snapshot;
   never silently replace values.
6. Rebuild generated benchmark CSVs from checksum-verified publisher inputs when applicable.
7. Run lint, type checks, tests, Stage 0 validation, and Stage 1 validation.
8. Record conclusion-changing changes in `registries/change_log.csv` and deviations in
   `registries/deviation_log.csv`.

## Current correction

The clean Stage 1 bibliography uses DOI `10.1051/0004-6361/201424313` for Kallinger et al. (2014).
The source-document bibliography contains a different suffix; it remains untouched as an immutable
project source and the discrepancy is documented in the audit.

