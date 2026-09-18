# Contributing

Contributions are welcome when they preserve the registered scientific design.

1. Open an issue with a Stage/Task ID and the affected hypothesis or deliverable.
2. Branch as `feature/Sxx-Txx-short-name`, `fix/Sxx-Txx-short-name`, or
   `docs/Sxx-Txx-short-name`.
3. Add or update tests and provenance records with the change.
4. Run `ruff`, `mypy`, `pytest`, the smoke workflow, and `validate-stage0`.
5. Open a pull request using the repository template. Never include raw mission data, secrets,
   or holdout labels.

Scientific changes require a change request in `registries/change_log.csv`. A correctness repair
after holdout access is allowed but must rerun every affected output and cannot be described as a
new confirmatory result without independent data.

The complete branch, review, authorship, decision, and ID policies are in
`docs/governance/GOVERNANCE.md`.

