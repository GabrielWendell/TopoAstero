## Stage and task

- Stage/task ID:
- Hypothesis/deliverable affected:
- Linked issue/change request:

## What changed

Describe the implementation and the scientific or reproducibility reason.

## Scientific-control checklist

- [ ] No final-holdout information was used for selection or tuning.
- [ ] Baseline, null, ablation, localization, and uncertainty impacts are stated.
- [ ] Configuration/schema/version changes are explicit and hashed.
- [ ] Negative or failed outcomes remain in the ledger.
- [ ] A change request exists if a headline conclusion could change.

## Verification

- [ ] `uv run ruff check .`
- [ ] `uv run mypy src`
- [ ] `uv run pytest`
- [ ] `uv run topoastero smoke --config configs/smoke.yaml --output-dir results/smoke`
- [ ] `uv run topoastero validate-stage0 --root .`
- [ ] New or changed outputs have manifests/checksums.

## Review roles

- Producing contributor:
- Code/data reviewer:
- Methods reviewer required? Why/why not?
- Supervisor approval required? Why/why not?

