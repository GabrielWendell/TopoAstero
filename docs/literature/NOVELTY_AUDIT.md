# Reproducible novelty audit

## Protocol and execution

The authoritative execution log is `evidence/search/novelty_search_log.csv`. On 2026-09-19 the
following six concepts were searched independently in arXiv and OpenAlex; the same requests to
Semantic Scholar were recorded as access-limited after HTTP 429 responses:

1. “topological echelle”;
2. “persistent homology” AND asteroseismology;
3. “topological data analysis” AND “solar-like oscillations”;
4. “persistent homology” AND “stellar oscillations”;
5. “persistent homology” AND “Kepler light curves”; and
6. “persistent homology” AND “asteroseismic estimator”.

The log preserves the exact request URL, service, scope, date, status, total count where returned,
number manually screened, direct-precedent count, outcome, and limitation. A failed query has blank
counts and can never be converted into a zero result.

## Screening test

A result is a direct precedent only if it combines all three:

- persistent homology or an equivalent filtration-based topological summary;
- solar-like oscillation or asteroseismic data/simulation; and
- estimation or validated detection of `numax`, `dnu`, mode/ridge structure, or the proposed
  topological-echelle task.

Cosmology, morphology, exoplanet classification, generic time-series periodicity, and use of the
word “homology” in stellar evolution are adjacent or false-positive results.

## Outcome

- arXiv returned zero records for all six exact concept queries.
- OpenAlex returned broad result sets for five queries and one result for the most specific query;
  the recorded top results contained no direct precedent.
- Semantic Scholar was rate limited and contributes no negative evidence.
- Primary adjacent evidence was retained in the gap map rather than discarded.

Thus G1 passes as a dated search result. It is not a universal absence claim.

## Re-run procedure

Quarterly and before submission, copy the six concept rows forward with a new audit ID and date;
run all available services; screen at least the first 20 results for broad queries and every result
when fewer than 20 are returned; deduplicate by DOI/title; preserve failed-service rows; update the
gap memorandum; and run `topoastero validate-stage1 --root .`.

