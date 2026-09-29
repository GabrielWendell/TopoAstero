# Independent proof review packet for G9

**Status:** Awaiting independent human review. This packet is ready for a
named mathematician with no authorship of these proofs or regressions.

Read the definitions and S9-T1 proof in
`docs/science/STAGE9_THEOREMS_AND_PROOFS.md`, the adversarial catalog, and
the proof-linked unit tests and numerical audit. The reviewer should:

1. Confirm the circular-distance lower and upper inequalities with worst-case
   curvature and two independent phase localization errors.
2. Verify the exact meaning of consecutive *trial* rows and explain why
   half/double aliases, dropped orders, pruning and competing tracks cannot
   be covered by a target-track statement.
3. Check that the coherence ceiling follows from Stage 8's actual formula
   and is **never** advertised as a ceiling on a maximum over other tracks or
   on the topological component.
4. Check the Gamma rates, fixed-mask diagram stability caveat, essential
   conventions, and explicitly independent stellar systematic allowances.
5. Reproduce `uv sync --locked --group dev`, `uv run pytest`, `uv run ruff
   check .`, `uv run mypy src`, the Stage 9 validator and audit workflow in a
   clean extracted copy. Record discrepancies and independent corrections.

The independent reviewer should update
`registries/stage9_proof_review.yaml` with a real name, affiliation,
independence attestation, review date, SHA-256 of the exact reviewed theorem
chapter, reviewed claim IDs, decision and
notes. This repository does not forge or infer such attestation from tests.
The `validate-stage9` command checks G9 coherence and calls the status
`review_pending` until an eligible accepted review is present. The empirical
informativeness of S9-T1 is limited to graph threshold design under its
hypotheses; the Stage 8 scientific utility verdict is not reopened.
