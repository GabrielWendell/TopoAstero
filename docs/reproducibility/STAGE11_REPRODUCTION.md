# Stage 11 commands and reproduction

Run from the TopoAstero root in Bash, PowerShell or a VS Code terminal.

## Check the delivered implementation

```text
uv sync --locked --group dev --extra astronomy
uv run python workflows/validate_stage11.py --root .
uv run python workflows/replay_stage11_reduced.py --root .
uv run pytest
```

The first validator passes the implementation while printing scientific G11
`population_pending`. Reduced replay recomputes the available observational
headline estimates from archived monthly spectra; it is not a full raw-data
reproduction or a population confirmation run. All prior stage checks remain
valid because the earlier byte-sealed sources were not edited.

## Acquire the population and run development

```text
uv run python workflows/run_stage11_legacy.py references --cache-dir ../legacy-reference-cache --download
uv run python workflows/run_stage11_legacy.py acquire --cache-dir ../topoastero-mission-cache --download
uv run python workflows/run_stage11_legacy.py run-development --cache-dir ../topoastero-mission-cache
uv run python workflows/run_stage11_legacy.py report
uv run python workflows/plot_stage11.py
```

Corrected derived reference tables are included, so the first command is only
needed to reacquire/rebuild them. It verifies the ReadMe's erratum designation.
Mission acquisition uses the original 2,159-product candidate inventory, checks
declared sizes, and records FIRST payload hashes explicitly. Candidate metadata
hashes are never treated as payload checksums. Later payload changes fail.
Fetching holdout payloads computes no holdout representation or estimate.

Full acquisition requires approximately 9.12 GB and considerably more processing
than Rudy. The exact inventory size is recorded in the cohort/acquisition tables.
Download by role with `--role development`, `--role internal_validation` or
`--role final_holdout` if preferred. This selection only limits downloads; all
cohort rows remain visible and failures are never removed from denominators.

For the supplied local Rudy cache, this reproduces the delivered non-holdout run:

```text
uv run python workflows/reproduce_stage11.py --cache-dir data/raw
uv run python workflows/plot_stage11.py
```

The source archive has only 10 Rudy Kepler monthly products. Their availability
is explicitly incomplete relative to the full Rudy inventory. The other 65
stars remain `missing_input`; none is replaced by a synthetic observation.
The delivered dev directories represent this acquisition snapshot. When adding
population products, make a NEW output directory after logging the change:

```text
uv run python workflows/run_stage11_legacy.py log-change --note "Completed population payload acquisition; rerun all non-holdout roles"
uv run python workflows/run_stage11_legacy.py run-development --cache-dir ../topoastero-mission-cache --output-dir results/stage11/population_dev
uv run python workflows/run_stage11_legacy.py report --development-dir results/stage11/population_dev
```

This preserves the delivered checkpoints. Supply that directory to `freeze`
with `--development-dir results/stage11/population_dev`. Existing checkpoints
with changed code/config/input hashes are rejected rather than overwritten.
The report command selects those active role results; after freeze, reports
automatically use the signed release's development directory.

## Freeze the exact confirmation release

The Stage 2 split policy requires supervisor and data-steward authorization.
Obtain those approvals after reviewing development/internal results; the
command records the actual approving identities. Do not invent them. No
confirmation has been opened in the delivered project.

Build the locked astronomy container and keep the private key outside the repo:

```text
docker build -f environment/stage11.Dockerfile -t topoastero-stage11 .
docker image inspect topoastero-stage11 --format "{{.Id}}"
openssl genpkey -algorithm RSA -pkeyopt rsa_keygen_bits:3072 -out ../stage11-release-private.pem
```

Use the actual `sha256:...` returned by Docker and actual approving names:

```text
uv run python workflows/run_stage11_legacy.py freeze --cache-dir ../topoastero-mission-cache --development-dir results/stage11/population_dev --supervisor "APPROVING SUPERVISOR" --data-steward "APPROVING DATA STEWARD" --container-digest "sha256:ACTUAL_IMAGE_DIGEST" --signing-key ../stage11-release-private.pem
```

Placeholders in this example must be replaced. Freeze refuses incomplete
acquisition, missing/pipeline-failed development results, stale evidence,
an existing release/opening, malformed image digests and private keys inside
the repository. OpenSSL is required for signing/verification, including on
Windows (available through standard OpenSSL installations or Git Bash).
The container is prepared for reproduction; it was not built in this workspace.
Do not edit code/configuration after signing or the opening preflight fails.

## Open confirmation once, then build final evidence

```text
uv run python workflows/run_stage11_legacy.py open-confirmation --cache-dir ../topoastero-mission-cache
uv run python workflows/run_stage11_legacy.py report
uv run python workflows/plot_stage11.py
uv run python workflows/validate_stage11.py --require-confirmation
```

After a process interruption, use the same command with `--resume`. Resume
retains every completed star, including scientific failures. It is unavailable
after completion. A machine crash can leave `stage11_confirmation.lease`:
record the incident separately, verify no process is running, remove only that
stale lease and resume. Never delete the state/archive to get a second opening.

## Outputs, performance and manuscript

`results/stage11/<role>/` contains one row per star/method/quantity, paired
performance/equivalence tables, operating-domain bins, ratio benchmarks,
summaries and evidence seals. `stars/KIC.../` contains the archived monthly
PSD matrix, mean PSD/background, bootstrap draws and analysis/window/alias
records. `reports/stage11/` contains G11, cohort, failure atlas, leakage audit,
traceability and figures. `paper2/` contains generated LaTeX source, status,
tables and bibliography. Compile the working manuscript after editing:

```text
cd paper2
pdflatex main
bibtex main
pdflatex main
pdflatex main
```

Missing observations and incomplete confirmation are reported candidly.
The all-positive selected cohort cannot establish specificity/FPR/probability
calibration. Cylinder/ridge inference remains geometric/reference-conditioned.
Do not interpret implementation PASS as completed scientific G11 or Paper II
publication readiness. `reports/stage11/task_traceability.csv` tracks all tasks.
