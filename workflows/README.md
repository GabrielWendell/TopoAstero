# Workflows

## Stage 10 / Paper I

`reproduce_stage10.py --cache-dir ../topoastero-mission-cache --download` is the full
public-ID entry point. It calls `run_stage10_rudy.py`, `build_stage10_evidence.py`,
`plot_stage10.py`, `build_stage10_paper.py` and `build_stage10_manifest.py` in order.
`--clean-check` creates a fresh source/environment/process and compares raw-product
reproduction with the frozen outputs. `replay_stage10_reduced.py` and
`validate_stage10.py` are offline checks. Independent human review remains separate.
See `docs/reproducibility/STAGE10_REPRODUCTION.md` for Windows/uv and TeX details.

Workflow files are thin, unattended entry points. Scientific logic lives in the package and is
unit-tested; notebooks call the same functions and are never authoritative.

- `smoke.py`: seeded analytic signal -> H0 persistence -> tables, figure, and manifest.
- `validate_stage0.py`: validates all frozen governance records and smoke evidence.
- `build_stage1_benchmarks.py`: checksum-verified publisher tables -> LEGACY/Rudy CSV evidence.
- `build_stage1_manifest.py`: rebuilds the Stage 1 deliverable checksum index.
- `validate_stage1.py`: validates all T1.1-T1.8 records, the G1 gate, and Stage 0 regression.
- `query_stage2_mast.py`: re-runs the dated Rudy MAST queries and inspects cached FITS payloads.
- `query_legacy_kepler_inventory.py`: freezes archive candidates for all 66 LEGACY stars.
- `acquire_stage2_products.py`: downloads and checksum-verifies frozen mission products.
- `build_stage2_reference_data.py`: checksum-verified publisher/Stage 1 sources -> canonical references.
- `build_stage2_examples.py`: creates canonical JSONL fixtures including a verified Q2 excerpt.
- `build_stage2_partitions.py`: regenerates the deterministic star-grouped partition and seal.
- `build_stage2_qc.py`: derives the pre-topology machine QC report.
- `build_stage2_manifest.py`: rebuilds the Stage 2 deliverable checksum index.
- `validate_stage2.py`: validates T2.1-T2.8, G2, and all earlier-stage regressions.
- `acquire_stage3_inputs.py`: downloads/verifies the 10 Kepler plus 11 SPOC TESS Stage 3 payloads.
- `run_stage3_classical.py`: one-command T3.1-T3.9 tables, figures, and run-manifest workflow.
- `build_stage3_manifest.py`: rebuilds the Stage 3 deliverable checksum index.
- `validate_stage3.py`: validates T3.1-T3.9, G3, and all earlier-stage regressions offline.
- `build_stage4_window_templates.py`: derives compact Kepler/TESS interval masks from verified
  external FITS payloads without redistributing fluxes.
- `run_stage4_simulation_lab.py`: executes T4.1-T4.9 tables, calibrated experiments, reports,
  publication-style figures, and the Stage 4 run manifest.
- `build_stage4_manifest.py`: rebuilds the Stage 4 deliverable checksum index.
- `validate_stage4.py`: validates T4.1-T4.9, G4, and all earlier-stage regressions offline.
- `run_stage5_tda_audit.py`: executes the five-representation pilot, backend checks, null and
  nuisance audits, redundancy/ablation analysis, localization figures, reports, and run manifest.
- `build_stage5_manifest.py`: rebuilds the Stage 5 deliverable checksum index.
- `validate_stage5.py`: validates T5.1-T5.8, G5, and all earlier-stage regressions offline.
- `run_stage6_psd_topology.py`: executes normalized PSD persistence, prominence equivalence,
  uncertainty-bearing `nu_max`/comb comparisons, null calibration, robustness, QC, and figures.
- `build_stage6_manifest.py`: rebuilds the Stage 6 deliverable checksum index.
- `validate_stage6.py`: validates T6.1-T6.8, G6, and all earlier-stage regressions offline.
- `run_stage7_delay_topology.py`: executes delay selection, missing-aware embeddings, VR diagrams,
  phase/IAAFT tests, classical ablations, rolling stability, figures, and the retain/drop decision.
- `build_stage7_manifest.py`: rebuilds the Stage 7 deliverable checksum index.
- `validate_stage7.py`: validates T7.1-T7.8, G7, and all earlier-stage regressions offline.
- `run_stage8_echelle.py`: generates the cylindrical echelle benchmark and bounded G8 verdict.
- `validate_stage8.py`: validates the Stage 8 geometry-only gate and prior-stage regressions.
- `run_stage9_mathematics.py`: regenerates exact/conditional proof-linked numeric audits,
  nine counterexample constructions, Gamma coverage, and styled figures with a fixed seed.
- `execute_stage9_notebook.py`: executes the small governed mathematics notebook offline.
- `build_stage9_manifest.py`: seals the outputs and preserves the independent-review hold.
- `validate_stage9.py`: checks T9.1-T9.8 implementation integrity and reports G9 separately.
- `repair_portability.py`: canonicalizes tracked text to LF, converts serialized repository paths to
POSIX form, and refreshes dependent Stage 0–9 checksums/seals without rerunning science.

Stage 3 and all later figure-producing workflows must use `topoastero.style` visual contract
`TA-PLOT-1.0`; the governance test rejects direct `savefig` calls in plotting workflows.


### Stage 11 additive commands

`run_stage11_legacy.py` exposes references/acquire/cohort/run-development/log-change/
freeze/open-confirmation/report/validate. `reproduce_stage11.py` runs all non-holdout
roles from verified inputs; `replay_stage11_reduced.py` recomputes stored monthly
PSD headlines offline; `plot_stage11.py` exports role-aware academic figures;
`validate_stage11.py` validates implementation and optionally scientific confirmation.
See `docs/reproducibility/STAGE11_REPRODUCTION.md` for commands and sequencing.
