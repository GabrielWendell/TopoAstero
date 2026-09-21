# Stage 1 completion report

**Stage:** Literature evidence map and benchmark specification (T1.1-T1.8)  
**Evidence date:** 2026-09-19  
**Gate:** G1 PASS with a bounded no-direct-precedent conclusion

## Delivered result

Stage 1 converts the literature review into checked, linked data rather than an informal reading
list. It supplies five specialist evidence maps, a 25-record synthesis matrix, an exact H1-H6
classical-baseline crosswalk, a dated novelty-search log, a claim-level reference audit, and a
reproducible benchmark specification.

The benchmark layer contains all 66 LEGACY stars, 264 authoritative global/atmospheric target rows,
12 explicitly context-only Rudy rows, and all 42 published Rudy mode frequencies. Publisher inputs
are represented by source URL, retrieval date, and SHA-256 digest without redistributing them.

## Scientific decisions

- The authoritative Rudy global values are the full LEGACY Table 3 values; Lightkurve tutorial
  outputs remain a context baseline because they use four quarters and publish no uncertainty.
- The retrieved Paper II Table 4 row is retained but is context-only because the flat file does not
  identify its originating modelling pipeline.
- “Topological echelle” and PH seismic estimators are candidate representations to evaluate rather
  than established methods or guaranteed discoveries.
- A topology claim is inadmissible without the baseline named in the H1-H6 crosswalk.
- A failed or rate-limited novelty query cannot be encoded as zero results.

## Verification commands

```bash
uv sync --locked --group dev
uv run ruff check .
uv run mypy src
uv run pytest
uv run topoastero validate-stage0 --root .
uv run topoastero validate-stage1 --root .
uv build
```

## Verification result

| Check | Result |
| --- | --- |
| locked dependency resolution | PASS; 19 packages |
| Ruff | PASS |
| strict mypy | PASS; 13 source files |
| pytest | PASS; 32 tests |
| branch-aware coverage | PASS; 85.74% in the working tree |
| Stage 0 validator | PASS |
| Stage 1 validator | PASS |
| wheel and source distribution | PASS; version 0.2.0 |
| clean source-distribution replay | PASS; both gates and 32 tests |

The Stage 1 validator checks the Stage 0 contract as a regression precondition. The clean replay
uses only the built source distribution and locked environment.

## Known limitations

- The novelty result is limited to the recorded index coverage and screening depth. Semantic
  Scholar was rate limited and is preserved as access-limited evidence.
- The 66-star LEGACY sample is high signal-to-noise and not population representative.
- Full population mode tables and immutable mission product manifests remain Stage 2 work.
- Table 4 stellar-model context values require publisher-side pipeline attribution before they can
  become benchmark targets.

## Recommendation

Proceed to Stage 2 while keeping the quarterly literature refresh due 2026-12-19. If a direct
precedent appears, apply the novelty-redefinition rule before making further novelty claims.
