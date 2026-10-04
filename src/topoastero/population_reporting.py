"""Source-backed Stage 11 evidence, honest G11 status, and an editable Paper II draft."""

from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Any

from topoastero.config import content_hash
from topoastero.population_freeze import release_issues
from topoastero.population_pipeline import cohort
from topoastero.population_store import (
    contained,
    read_json,
    seal,
    seal_issues,
    write_json,
    write_table,
)
from topoastero.portability import write_text_lf


def build_report(root: Path, cfg: dict[str, Any], *, development_dir: Path | None = None) -> dict[str, Any]:
    members = cohort(root, cfg)
    report = contained(root, cfg["reports"])
    output = contained(root, cfg["output"])
    releasepath = contained(root, cfg["release"])
    release = read_json(releasepath) if releasepath.exists() else None
    development = contained(root, release["payload"]["development_directory"]) if release else (development_dir or output)
    role_directories = {name: (output / name if name == "confirmation" else development / name).resolve().relative_to(root.resolve()).as_posix()
                        for name in ("development", "internal_validation", "descriptive_benchmark", "confirmation")}
    report.mkdir(parents=True, exist_ok=True)
    acquisition = read_json(contained(root, cfg["acquisition"]))
    available = Counter(r["stable_star_id"] for r in acquisition["products"] if r["status"] == "payload_verified")
    for row in members:
        row["acquired_products"] = available[row["stable_star_id"]]
        row["acquisition_status"] = "complete" if available[row["stable_star_id"]] == row["candidate_products"] else "incomplete"
    write_table(report / "cohort_ledger.csv", members)
    role_summaries = {}
    evidence = []
    for name in ("development", "internal_validation", "descriptive_benchmark", "confirmation"):
        directory = contained(root, role_directories[name])
        path = directory / "summary.json"
        if path.exists():
            role_summaries[name] = read_json(path)
            manifest = read_json(directory / "run_manifest.json")
            issues = seal_issues(root, manifest["files"])
            if issues:
                raise ValueError("; ".join(issues))
            evidence.append(seal(root, directory / "run_manifest.json"))
    statepath = contained(root, cfg["confirmation_state"])
    state = read_json(statepath) if statepath.exists() else {"status": "unopened", "opening_count": 0}
    frozen = release is not None and release_issues(root, cfg, release) == []
    completed = state["status"] == "completed" and "confirmation" in role_summaries
    incomplete = [r["stable_star_id"] for r in members if r["acquisition_status"] != "complete" and not r["exclusion"]]
    holds = []
    if incomplete:
        holds.append("population_payload_acquisition_incomplete")
    if not frozen:
        holds.append("confirmation_release_not_frozen")
    if not completed:
        holds.append("one_time_confirmation_not_completed")
    elif role_summaries["confirmation"]["stars_with_estimates"] < cfg["statistics"]["minimum_stars_for_interval"]:
        holds.append("insufficient_confirmation_stars_for_population_inference")
    # Geometric ridge scores and positive-only conditional calibration remain narrower claims.
    limitations = ["G8_geometry_only_no_blind_ridge_ratios", "positive_only_cohort_no_specificity_or_false_alarm_rate",
                   "conditional_monthly_bootstrap_no_joint_stellar_posterior", "reference_covariance_unavailable",
                   "G9_G10_independent_external_reviews_pending", "no_individual_evolutionary_classification"]
    gate = {"schema_version": 1, "stage_id": cfg["stage_id"], "implementation_status": "pass",
            "status": "population_pending" if holds else "pass_with_limitation",
            "scientific_population_gate_passed": not holds, "holds": holds, "limitations": limitations,
            "cohort_stars": 66, "acquired_products": acquisition["verified_products"], "expected_products": acquisition["expected_products"],
            "stars_with_complete_acquisition": 66 - len(incomplete), "partition_counts": dict(Counter(r["role"] for r in members)),
            "confirmation_status": state["status"], "holdout_opening_count": state["opening_count"],
            "publication_ready": False, "claim_scope": "population_measurement_pending" if holds else "conditional_star_grouped_validation",
            "role_directories": role_directories,
            "configuration_sha256": content_hash(cfg)}
    write_json(report / "G11_ACCEPTANCE.json", gate)
    audit = {"schema_version": 1, "grouping": "one_row_per_star_method_quantity", "partition_counts": gate["partition_counts"],
             "partition_integrity": "original_stage2_sha256_verified", "role_pooling": False,
             "development_holdout_access": False, "holdout_public_metadata_visible": True,
             "holdout_observation_access": completed or state["status"] == "running",
             "holdout_opening_count": state["opening_count"], "release_valid": frozen,
             "multiplicity": "two_registered_endpoints_Holm_on_paired_TOST; missing_endpoint_p1",
             "subgroup_inference": "fixed_bins_descriptive_only_no_multiple_subgroup_significance_tests",
             "missingness": "all_star_denominators_and_reason_flags_retained", "repeated_months_count_as_stars": False,
             "reference_uncertainty": "asymmetric_intervals_preserved_no_sigma_conversion",
             "ratio_reference_edition": read_json(contained(root, cfg["reference_manifest"]))["edition"],
             "procedural_boundary": "local guard_is_not_cryptographic_identity_blinding_or_remote_access_control"}
    write_json(report / "leakage_multiplicity_audit.json", audit)
    reasons = []
    for role, summary in role_summaries.items():
        for row in summary["statuses"]:
            for flag in row["flags"]:
                reasons.append({"role": role, "stable_star_id": row["stable_star_id"], "status": row["status"], "reason_code": flag})
    write_table(report / "failure_atlas.csv", reasons, ["role", "stable_star_id", "status", "reason_code"])
    tasks = [
        ("T11.1", "cohort_ledger.csv; corrected_reference_manifest", "metadata_complete_payloads_pending" if incomplete else "complete"),
        ("T11.2", "results/stage11/<role>/catalog.csv; per_star_mean_PSD_window_background", "implemented_population_pending" if incomplete else "executed"),
        ("T11.3", "per_star_analysis.json; prominence_control; alias_scans; geometry_only_echelle", "implemented_population_pending" if incomplete else "executed"),
        ("T11.4", "registries/stage11_qa.jsonl; checksum_checked_resumable_development", "implemented"),
        ("T11.5", "signed_confirmation_release; exact_code_config_environment_container_and_exclusion_seals", "frozen" if frozen else "ready_not_frozen"),
        ("T11.6", "one_time_open_confirmation; atomic_state; first_completed_archive", "completed" if completed else "ready_unopened"),
        ("T11.7", "performance.csv; paired_comparisons.csv; coverage_and_failure_counts", "implemented_confirmation_pending" if not completed else "executed"),
        ("T11.8", "operating_domain.csv; failure_atlas.csv; sparse_cell_suppression", "implemented_confirmation_pending" if not completed else "executed"),
        ("T11.9", "ratio_benchmark.csv; corrected_ratios; degree_order_conditioned_localization", "implemented_blind_ratios_withheld"),
        ("T11.10", "leakage_multiplicity_audit.json; access_and_QA_logs; release_verification", "implemented_confirmation_pending" if not completed else "executed"),
        ("T11.11", "paper2/main.tex; generated_status_and_tables; references.bib", "evidence_aware_draft"),
    ]
    write_table(report / "task_traceability.csv", [{"task_id": t, "evidence": e, "status": s} for t, e, s in tasks])
    lines = ["# Stage 11 - Kepler LEGACY population validation", "",
             f"Implementation: {gate['implementation_status']}. Scientific G11: {gate['status']}.", "",
             f"The frozen cohort contains 66 stars: {gate['partition_counts']}. Acquired {acquisition['verified_products']} of {acquisition['expected_products']} candidate products.",
             f"Confirmation status: {state['status']}; observed opening count: {state['opening_count']}.", "",
             "Results are separated by role. Rudy remains descriptive and is excluded from population confirmation performance.",
             "Missing stars have four explicit catalog rows, two methods by two quantities. Failed/rejected estimates are not imputed.", "",
             "Parameter errors use a shared successful star set; method-specific valid/failed/limited counts are reported alongside it.",
             "Population intervals resample stars jointly; stellar intervals resample nonoverlapping months jointly and refit backgrounds.",
             "Coverage compares conditional intervals to published reference centers; interval overlap is reported separately. It is not coverage of a known true stellar parameter.",
             "The LEGACY sample contains selected oscillators. Specificity, false-alarm rate, Brier score and probability calibration cannot be measured from these positive-only observations.",
             "Cylinder scores remain geometric diagnostics. Delay PH stays dropped. H0/prominence differences are independently checked.",
             "Reference ratio localization is conditioned on published degrees and orders. No blind r02/r01/r10 estimate is issued. Corrected asymmetric uncertainties are retained; covariance-based intervals are withheld.", "",
             "An exact signed release and recorded supervisor/steward authorization precede one-time confirmation. Repeated opens, changed code/configuration and stale inputs are rejected.",
             "Process interruption can resume the identical attempt; completed star results, including failures, are never selectively rerun.", "",
             "See docs/reproducibility/STAGE11_REPRODUCTION.md for executable commands and docs/protocols/STAGE11_POPULATION_PROTOCOL.md for the analysis contract."]
    write_text_lf(report / "STAGE11_REPORT.md", "\n\n".join(lines) + "\n")
    write_text_lf(report / "TRACEABILITY_MATRIX.md", "# Stage 11 traceability\n\n| Task | Evidence | State |\n| --- | --- | --- |\n" + "\n".join(f"| {t} | {e} | {s} |" for t, e, s in tasks) + "\n")
    write_json(report / "evidence_manifest.json", {"schema_version": 1, "files": evidence, "role_directories": role_directories,
                                                "report_files": [seal(root, report / name) for name in ("G11_ACCEPTANCE.json", "cohort_ledger.csv", "failure_atlas.csv", "leakage_multiplicity_audit.json", "task_traceability.csv")]})
    build_paper(root, cfg, gate, role_summaries)
    return gate


def build_paper(root: Path, cfg: dict[str, Any], gate: dict[str, Any], summaries: dict[str, Any]) -> None:
    paper = root / "paper2"
    paper.mkdir(exist_ok=True)
    observed = sum(s["stars_with_estimates"] for s in summaries.values())
    status = gate["status"].replace("_", r"\_")
    write_text_lf(paper / "results_status.tex", f"\\newcommand{{\\GateStatus}}{{{status}}}\n\\newcommand{{\\ObservedStars}}{{{observed}}}\n\\newcommand{{\\PayloadCount}}{{{gate['acquired_products']}}}\n")
    tables = [r"\begin{tabular}{lrrr}", r"Role & Stars & Measured & Missing/failed \\", r"\hline"]
    for role, summary in summaries.items():
        label = role.replace("_", r"\_")
        tables.append(f"{label} & {summary['stars']} & {summary['stars_with_estimates']} & {summary['stars'] - summary['stars_with_estimates']} " + r"\\")
    tables.append(r"\end{tabular}")
    write_text_lf(paper / "results_tables.tex", "\n".join(tables) + "\n")
    text = r"""\documentclass[11pt]{article}
\usepackage[margin=25mm]{geometry}
\usepackage{amsmath,booktabs,graphicx,hyperref}
\input{results_status}
\title{Persistent spectral localization and cylindrical geometry across the Kepler LEGACY sample}
\author{Gabriel Wendell}
\date{Stage 11 evidence-aware working draft}
\begin{document}\maketitle
\begin{abstract}
We define a star-grouped validation of localized power-spectrum persistence and
classical seismic estimators for the 66-star Kepler LEGACY cohort. The current
scientific gate is \GateStatus. The archived development evidence contains
\ObservedStars{} stars with estimates and \PayloadCount{} verified mission products.
Population generalization is not established until the signed confirmation release
is executed once. This draft states the construction, planned comparisons and
current limitations without substituting missing measurements with simulations.
\end{abstract}
\section{Population and observation operator}
Use the existing grouped split: 39 development, 13 internal validation, 13 final
holdout stars and the previously studied descriptive benchmark Rudy. Monthly
PDCSAP light curves follow PP-01. A common physical frequency grid is rebinned
without extrapolation; monthly spectra are averaged with retained-exposure weights.
Published global references are traceable to Silva Aguirre et al. (2017);
mode/ratio references use the corrected Lund et al. (2017) erratum edition.
The observational references are documented in
\cite{SilvaAguirre2017,Lund2017,Lund2017Erratum}.
\section{Construction and controls}
For a background-normalized scalar spectrum, path-superlevel $H_0$ persistence
equals elder-rule peak prominence on the shared domain. We therefore report the
independent prominence check as a mandatory control. A persistence-weighted peak
centroid estimates $\nu_{\max}$ within a data-selected envelope. Comb trials around
the classical spacing retain half, nominal and double alternatives. Cylinder
scores compare periodic ridge geometry and finite $H_0$ localization but do not
establish independent spectral information or blind degree identification.
\section{Statistical analysis}
The primary endpoints are errors in $\nu_{\max}$ and $\Delta\nu$. Both methods use
the same successful stars; method-specific missingness, failures and catastrophic
errors are displayed beside bias, MAE and RMSE. Star bootstrap draws are paired.
Practical equivalence uses paired TOST on absolute fractional-loss differences,
with registered margins 0.01 and 0.005 and Holm correction across both endpoints.
Small-cell operating domains remain descriptive. Monthly intervals refer to the
mean-spectrum estimator; reference-center coverage and reference-interval overlap
are distinct quantities. A positive-only selected cohort cannot estimate
specificity, false-alarm rates or probability calibration.
\section{Current evidence and confirmation state}
\input{results_tables}
\par\medskip
Machine-readable catalogs and reason-coded failure/operating-domain tables are
generated separately for each role. The one-time holdout archive will supply final
performance estimates; no population superiority claim is currently supported.
\section{Ridge ratios and counterexamples}
The degree/order-conditioned mode-localization benchmark compares $r_{02}$ and
related ratios to corrected individual-frequency references. It is explicitly
reference-conditioned. Unanchored ridges, alias ambiguity, sparse orders,
background instability and missing observations are failure cases, not suppressed
examples. A ratio of median frequencies need not equal the median ratio.
No covariance-based ratio interval is claimed without covariance data.
\section{Domain of validity and reproducibility}
This benchmark concerns selected main-sequence and mildly evolved solar-like
LEGACY oscillators. Extrapolation to undetected oscillators, red giants or TESS
requires separate validation. Delay topology remains dropped after Stage 7;
cylindrical inference remains geometry-only after Stage 8. Earlier independent
proof and human reproduction reviews remain pending. Code, environment, inputs,
exclusions, thresholds and statistical rules must be signed and frozen before
confirmation. Public identifiers are visible; local guards are procedural access
controls, not cryptographic blinding. See the Stage 11 protocol, reproduction
guide and task traceability for commands and exact archived evidence.
\bibliographystyle{plain}\bibliography{references}
\end{document}
"""
    write_text_lf(paper / "main.tex", text)
    write_text_lf(paper / "references.bib", (root / "paper1/references.bib").read_text() + "\n@article{Lund2017Erratum, author={Lund, M. N. and others}, title={Erratum: Standing on the Shoulders of Dwarfs}, journal={The Astrophysical Journal}, volume={850}, pages={110}, year={2017}, doi={10.3847/1538-4357/aa9658}}\n")
    write_text_lf(paper / "README.md", "# Paper II working draft\n\nRegenerate with the Stage 11 `report` command. All status/tables come from archived role results; confirmation-pending drafts make no population performance claim. Compile with `pdflatex main`, `bibtex main`, `pdflatex main`, `pdflatex main` after reviewing and expanding the scientific discussion.\n")
