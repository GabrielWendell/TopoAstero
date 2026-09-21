# Workflows

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
- `repair_portability.py`: canonicalizes tracked text to LF, converts serialized repository paths to
  POSIX form, and refreshes dependent Stage 0--4 checksums/seals without rerunning science.

Stage 3 and all later figure-producing workflows must use `topoastero.style` visual contract
`TA-PLOT-1.0`; the governance test rejects direct `savefig` calls in plotting workflows.
