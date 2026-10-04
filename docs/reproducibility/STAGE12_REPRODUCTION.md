# Stage 12 commands and reproduction

Run from the project root in Bash, PowerShell, or a VS Code terminal. The existing package/dependency versions remain unchanged so prior estimator snapshots retain their identities. Stage 12 is an additive `topoastero.hybrid` package.

```text
uv sync --locked --group dev --extra astronomy
uv run python workflows/validate_stage12.py --root .
uv run python workflows/replay_stage12_reduced.py --root .
uv run pytest
```

The validator distinguishes implementation PASS from scientific G12 `validation_pending`. Reduced replay recomputes the grouped models and OOF predictions from archived, observed Stage 11 features; it opens no holdout and does not regenerate raw transfer data.

## Supplied raw-data pilot

```text
uv run python workflows/reproduce_stage12.py --cache-dir data/raw
uv run python workflows/plot_stage12.py
```

Completed checkpoint IDs and hashes must match exactly; rerunning these commands verifies/reuses those results. The first raw pilot processes all 11 actual sectors, the registered combinations and 192 degradation cells (3 sector windows x 2 offsets x 4 draws x 8 levels). Time/flux arrays are under `results/stage12/degraded/`. Expect this to take minutes rather than an offline validation's seconds; duration depends on available CPU and storage. The raw adapter imports the existing optional Lightkurve/Astropy dependencies. No network download occurs in the Stage 12 commands.

## New acquisition or full transfer preset

The supplied population raw cache is incomplete locally; nine development spectra are available as derived observations. Do not treat the 1,261 previously acquired product records as 1,261 local raw files. Complete Stage 11 acquisition and development QA using its guide before population confirmation.

When inputs or code/configuration change, preserve the delivered results and set NEW output/report directories in `configs/stage12_hybrid.yaml`, e.g. `results/stage12/full_v1` and `reports/stage12/full_v1`. For the full fixed transfer design, change `transfer.profile` to `full`; it uses all 11 sector masks and 32 draws, yielding 5,632 cells. Log the change with a new analysis record before running:

```text
uv run python workflows/run_stage12_hybrid.py fit
uv run python workflows/run_stage12_hybrid.py transfer --cache-dir data/raw
uv run python workflows/run_stage12_hybrid.py report
uv run python workflows/plot_stage12.py
```

Fold construction, features, penalties, margins and quality rules remain locked. A higher number of same-star draws does not increase the independent population size. Avoid running multiple writers against the same output directory. Memory usage is bounded per cell; checkpoints and degraded arrays are written incrementally.

## Signed model release and final confirmation

The current nine-star pilot cannot be frozen for a scientific population confirmation: the guard requires at least 20 independent development stars. Complete Stage 11 development first. Obtain actual approving supervisor/steward identities after reviewing the model card and supporting evidence. Build the container and retain the private key outside the repository:

```text
docker build -f environment/stage12.Dockerfile -t topoastero-stage12 .
docker image inspect topoastero-stage12 --format "{{.Id}}"
openssl genpkey -algorithm RSA -pkeyopt rsa_keygen_bits:3072 -out ../stage12-model-private.pem
```

Use the actual image digest and actual approving names:

```text
uv run python workflows/run_stage12_hybrid.py freeze --signing-key ../stage12-model-private.pem --supervisor "ACTUAL APPROVING SUPERVISOR" --data-steward "ACTUAL APPROVING STEWARD" --container-digest "sha256:ACTUAL_IMAGE_DIGEST"
```

Replace every placeholder. No real release was signed and no Docker image was built for the delivered pilot. OpenSSL is required on the operator's system. Freeze Stage 12 BEFORE using Stage 11's `open-confirmation`; see the Stage 11 guide for its distinct acquisition/signing requirements. Once Stage 11 has produced its first validated confirmation archive:

```text
uv run python workflows/run_stage12_hybrid.py evaluate-confirmation
uv run python workflows/run_stage12_hybrid.py report
```

This applies the fixed Stage 12 models once; it does not reopen raw holdout light curves or fit/tune on final stars. Existing Stage 12 confirmation state prevents repeated scoring. Do not delete a running/completed state to retry. An interruption requires a documented incident and preservation of the first attempt; the automated workflow does not grant an unrestricted rerun.

## Separately authorized recalibration

Recalibration is not applied by default. Prepare a JSON object with a `rows` array (or CSV) containing: `stable_star_id`, `role`, `origin`, `method`, `quantity`, `estimate`, `reference`. `role` must be `development`, `origin` must be `degradation_simulation`; both methods/endpoints must exist for every non-Rudy parent star. At least 10 independent parents are needed. Then, before signing/opening:

```text
uv run python workflows/run_stage12_hybrid.py recalibrate --simulations path/to/development_simulations.json --authorization "ACTUAL AUTHORIZATION RECORD AND RATIONALE"
```

The prespecified log-offset layer is archived, included in release seals, and used for a NEW transfer run. Evaluate it on disjoint simulation stars before claiming successful recalibration. It changes no features and does not restore TESS risk-probability or interval calibration. Signed/opened releases cannot be recalibrated. Use a new configured output directory rather than rewriting the delivered transfer archive.

## Evidence and manuscript

`models.json`, `feature_dataset.json`, `fold_audit.json`, `oof_predictions.csv`, `increment.json` and `probability_calibration.json` are under the configured output directory. Transfer curves, actual sectors/combinations, degraded arrays and source hashes are alongside them. Reports include G12, model card, task traceability, scope decision and recalibration note. Inherited source-archive issues and repairs are recorded in `reports/stage12/INHERITED_REPAIRS.md`; old Stage 11 runs remain available.

Compile the editable Paper III draft:

```text
cd paper3
pdflatex main
bibtex main
pdflatex main
pdflatex main
```

Passing tests verifies implementation and evidence consistency. It does not complete missing acquisition, independent review, probability calibration, signed confirmation or a powered population transfer study.

The optional log-offset layer applies only to TESS-like transfer predictions. It never changes native Kepler predictions or the primary Kepler LEGACY confirmation archive. A TESS calibration requires disjoint transfer-simulation validation; successful Kepler confirmation is not evidence that this transfer calibration works.
