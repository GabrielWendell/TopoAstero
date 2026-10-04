# Inherited archive issues and bounded repairs

The supplied `TopoAstero_Stage11_Implemented.zip` is the implementation base. A baseline run in the locked Python 3.12 environment collected 400 tests: 375 passed and 25 failed, with 85.06% overall coverage. The original test output and administrative records are preserved under `reports/stage12/inherited_snapshot/`.

The failures were reproducible archive issues: stale byte seals in Stage 0–9 indexes and Stage 9's run manifest, an unrun Stage 10 reproduction/G10 administrative gate, stale Stage 11 estimator fingerprints, and a governance assertion that required a successful Rudy Stage 11 estimate although the uploaded archive contains a Rudy pipeline failure. They were not treated as evidence that the missing population observations succeeded.

## Portability and administrative seals

The existing `workflows/repair_portability.py`, `build_stage9_manifest.py` and `build_stage10_manifest.py` refresh byte seals after authorized additions. The only inherited text file needing LF normalization was `docs/protocols/STAGE11_LEGACY_FIX.md`. Reference-table content, cohort partitions, split attestation, previous numerical estimators, their configuration and dependency versions were preserved. G9/G10 independent review remains pending. Updating a checksum index does not supply scientific validation or a human review signature.

## Actual Stage 10 reproduction

The existing `workflows/check_stage10_portable_reproduction.py` was executed in a fresh source/work directory using the 21 supplied, checksum-verified raw Rudy products. Its 46 scientific/figure/manuscript comparisons passed the helper's declared numerical tolerances (absolute and relative 1e-6), with the registered portable figure comparison. The resulting machine reproduction record replaces the supplied `not_run` administration; the original records remain in the inherited snapshot. The strict prior record and detailed portable comparison are also retained under `reports/stage11/`. This was automated reproduction in this environment, not independent human review, Docker reproduction or an external approval.

## Stage 11 archived-spectrum replay

`workflows/repair_stage12_inherited.py` re-executed the current Stage 11 analysis and 128 monthly bootstrap draws for the nine available development stars and one available internal-validation star from their archived monthly spectra. It wrote a NEW `results/stage11/stage12_compatibility_replay_v2/` directory and selected it in the Stage 11 evidence manifest. Original `results/stage11/development/`, `internal_validation/`, `descriptive_benchmark/` and `population_dev/` runs remain available.

The population raw cache is external and incomplete in this ZIP. This replay did not reproduce population raw acquisition, time-series preprocessing or periodogram construction. Its metadata explicitly says `archived_monthly_spectra_only_no_raw_payload_reproduction` and `raw_payloads_reprocessed: false`. Existing failed/missing/excluded records, including Rudy's Stage 11 failure, were preserved rather than relabeled as new successful observations. Catalogs and the Paper II evidence tables were regenerated from this honestly bounded active archive. A QA event records the scope.

The affected Stage 11 governance test now reads the active evidence directory and checks that the summary's successful-star count equals the catalog's actual measured-star count, while still requiring exactly one descriptive Rudy star and no holdout use. It no longer asserts a fabricated successful measurement.

## Stage 12 scope

The full lint check also identified redundant `socket.timeout` aliases and a quoted future annotation in the supplied Stage 11 acquisition source/tests. These were replaced with the identical Python 3.11+ built-in `TimeoutError` and ordinary postponed annotation; no numerical estimator behavior changed. Because prior fingerprints cover acquisition source, the available Stage 11 derived spectra were genuinely replayed again into the v2 compatibility directory. The first compatibility replay remains preserved.

Stage 12 modules live in the new `topoastero.hybrid` subpackage; frozen prior estimator source modules and dependency versions remain unchanged. All model fitting uses the nine available development stars. The transfer pilot uses the locally supplied Rudy Kepler/TESS data and archives every physical degraded array and analysis checkpoint. No real release key/approval was created, no final holdout was opened, no recalibration was authorized, and no publication or broader TESS expansion is claimed. Synthetic release fixtures are test data only.
