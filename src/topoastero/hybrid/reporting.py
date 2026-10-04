"""Evidence-aware G12, model card, scope decision and editable Paper III."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from topoastero.hybrid.features import CLASSICAL, TOPOLOGY, fingerprint
from topoastero.population_store import (
    contained,
    read_json,
    seal,
    write_json,
    write_table,
)

TASKS = (
    ("T12.1", "registries/stage12_tasks.csv", "registered"),
    ("T12.2", "models.json;fold_audit.json", "nested_grouped_baseline"),
    ("T12.3", "models.json;registries/stage12_features.csv", "locked_three_feature_hybrid"),
    ("T12.4", "increment.json;probability_calibration.json", "OOF_pilot_no_population_claim"),
    ("T12.5", "MODEL_CARD.md;actual_tess.json", "reason_codes_probabilities_withheld_when_unsupported"),
    ("T12.6", "degraded/*.npz;degradation_cells.csv", "matched_physical_degradation"),
    ("T12.7", "transfer_curves.csv;actual_vs_degraded.json", "conditional_Rudy_trajectories"),
    ("T12.8", "actual_tess.json", "11_sectors_and_registered_PSD_combinations"),
    ("T12.9", "recalibration_note.json;calibration_layer_CLI", "implemented_disabled_without_authorization"),
    ("T12.10", "TESS_SCOPE_DECISION.json", "stop_broader_sample_pending_power_and_domain_evidence"),
    ("T12.11", "paper3/main.tex;main.pdf", "evidence_aware_working_draft"),
)


def build_report(root: Path, cfg: dict[str, Any]) -> dict[str, Any]:
    output, reports = contained(root, cfg["output"]), contained(root, cfg["reports"])
    run = read_json(output / "development_run.json")
    increment = read_json(output / "increment.json")
    transfer = read_json(output / "transfer_run.json") if (output / "transfer_run.json").exists() else None
    state_path = contained(root, cfg["confirmation_state"])
    state = read_json(state_path) if state_path.exists() else {"status": "unopened", "opening_count": 0}
    holds = []
    if run["usable_stars"] < cfg["minimum_claim_stars"]:
        holds.append("insufficient_independent_development_stars")
    prior = read_json(root / "reports/stage11/G11_ACCEPTANCE.json")
    if not prior["scientific_population_gate_passed"]:
        holds.append("G11_population_validation_pending")
    if state["status"] != "completed":
        holds.append("signed_Stage12_confirmation_pending")
    if not transfer or transfer["profile"] != "full":
        holds.append("full_transfer_randomization_pending")
    if not transfer or transfer["parent_stars"] < cfg["minimum_claim_stars"]:
        holds.append("single_star_transfer_not_population_power")
    confirmed = read_json(output / "confirmation_increment.json") if state["status"] == "completed" else {"rows": []}
    primary = confirmed["rows"] if confirmed["rows"] else increment["rows"]
    inference_holds = [h for h in holds if "transfer" not in h]
    quality_positive = bool(confirmed.get("quality", {}).get("positive_quality_increment", False))
    positive = bool(not inference_holds and ((len(primary) == 2 and all(r["positive_increment"] for r in primary)) or quality_positive))
    equivalent = bool(not inference_holds and len(primary) == 2 and all(r["quantified_equivalence"] for r in primary))
    gate = {"schema_version": 1, "stage_id": cfg["stage_id"], "implementation_status": "pass",
            "status": "positive_increment" if positive else ("quantified_redundancy" if equivalent else "validation_pending"),
            "positive_complementarity_claim": positive, "positive_population_transfer_claim": False,
            "usable_development_stars": run["usable_stars"], "registered_development_stars": run["registered_development_stars"],
            "transfer_parent_stars": transfer["parent_stars"] if transfer else 0, "actual_TESS_sectors": transfer["actual_sectors"] if transfer else 0,
            "confirmation_status": state["status"], "confirmation_opening_count": state["opening_count"],
            "holds": holds, "configuration_sha256": run["configuration_sha256"], "code_sha256": fingerprint(root),
            "publication_ready": False, "delay_PH": "dropped_at_G7", "cylinder_inference": "geometry_only"}
    write_json(reports / "G12_ACCEPTANCE.json", gate)
    write_json(reports / "TESS_SCOPE_DECISION.json", {"decision": "stop_at_Rudy_transfer_limits", "broader_TESS_expansion": False,
                                                    "reason": "No powered multi-star transfer evidence; candidate values and descriptive sectors do not establish detections.",
                                                    "required_for_expansion": ["supported_locked_population_increment_or_equivalence", "calibrated_failure_risk", "agreement_with_independent_actual_targets", "prospective_sample_power_and_acquisition_plan"]})
    layer_path = output / "authorized_calibration_layer.json"
    layer = read_json(layer_path) if layer_path.exists() else None
    write_json(reports / "recalibration_note.json", {"status": "authorized_layer_requires_disjoint_validation" if layer else "not_authorized_not_applied",
                                                   "applied": bool(transfer and transfer["recalibration_applied"]),
                                                   "authorization": layer["authorization"] if layer else None,
                                                   "prespecified_layer": "star_weighted_median_log_offset",
                                                   "training_role": "development_simulations_only", "Rudy_and_actual_test_sectors_forbidden": True,
                                                   "feature_redesign": False, "instruction": "Use separately authorized recalibrate command; retain and validate on disjoint simulation stars."})
    write_table(reports / "task_traceability.csv", [{"task_id": task, "evidence": evidence, "status": status} for task, evidence, status in TASKS])
    card = f"""# Stage 12 model card

The baseline and hybrid predict log corrections to conventional nu_max and Delta_nu. Development stars: {run['usable_stars']} usable / {run['registered_development_stars']} registered; failures remain in the cohort ledger. Models are fitted only on development stars. Rudy, internal-validation stars and the final holdout are excluded from fitting.

Conventional/control inputs: {', '.join(CLASSICAL)}. Hybrid additions: {', '.join(TOPOLOGY)}. Path H0 equals prominence; its location descriptor is included in BOTH models. The graph control is included in the baseline. Cylinder descriptors remain geometry-only. Any practical increment is conditional on this finite model class, not evidence of irreducible spectral information.

Both models share outer/inner star folds. Median imputation, scaling, penalties and residual/probability calibration use training stars only. Each star has total training weight one. Three regularization values are selected by inner validation. Regression intervals use inner OOF residual ranks, not exact split-conformal guarantees or joint stellar posteriors. Rank support can be insufficient, in which case intervals are null.

Catastrophic-failure and nominal-alias reliability probabilities are calibrated on inner OOF logits only if both classes and all relevant folds support fitting. Astrophysical detection probabilities are withheld for the positive-only cohort. TESS probabilities and Kepler-derived intervals are withheld under mission shift. Null means unavailable; it never means zero risk.

Reason codes: missing_or_weak_envelope, alias_ambiguity, domain_shift, outside_training_range, missing_predictor, unreliable_parameter, failure_probability_uncalibrated, mission_shift, model_unavailable, pipeline_failure, unsupported_window. These reasons are separate from calibrated probabilities. Candidate estimates are retained; acceptance and recoverability are reported separately. QC screening does not constitute an oscillation detection.

Paired primary utility is reduction in absolute fractional error, with margins 0.01 (nu_max) and 0.005 (Delta_nu). Paired star bootstrap intervals condition on the fitted OOF models; they do not include full training-selection uncertainty. The superiority family contains two regression endpoints and the conditional failure-Brier test; absent class support contributes p=1. Regression uses Holm and quality uses conservative three-test Bonferroni. Equivalence is a separate two-regression family. Secondary diagnostics are exploratory. Decision-curve benefit uses a declared failure-action threshold and counts false confidence.

The transfer benchmark uses one previously studied star. Repeated sectors, offsets, levels and draws are correlated observations of that star, never independent population units. Exposure integration rejects unsupported source gaps. Noise is added without subtracting inherited noise. Passband response and contamination are registered sensitivities; the code does not infer these astrophysical/instrument parameters from test labels. TESS PDCSAP processing can already correct dilution, so additional contamination is a sensitivity, not a claimed correction.

The source/model digest is checked before and throughout actual-sector processing. Actual Rudy sectors were already examined in Stage 10; this is a reproducible frozen-method case study, not a newly blinded validation set. Adjacent-sector combinations average PSDs incoherently with exposure weights; no phase stitching across years is attempted. No broader TESS program is authorized by this pilot.

Scientific G12: {gate['status']}. Publication readiness: false. Required upstream independent reviews remain explicit. See the protocol and reproduction guide for data contracts and signed confirmation procedures.
"""
    (reports / "MODEL_CARD.md").parent.mkdir(parents=True, exist_ok=True)
    (reports / "MODEL_CARD.md").write_text(card, encoding="utf-8")
    text = f"""# Stage 12 implementation and current evidence

Implementation PASS; scientific G12 `{gate['status']}`.

{run['usable_stars']} independent development stars have features, out of {run['registered_development_stars']} registered development stars. Missing/failed upstream observations remain visible. No holdout was opened for this implementation. The signed model release must precede any Stage 11 holdout opening; a release created after seeing that holdout is rejected.

The primary paired increments, calibration curves/decision curves (or explicit withholding), transfer trajectories, degraded light curves, actual Rudy cases and model card are machine-readable. The current holds are: {', '.join(holds)}.

The manuscript is an evidence-aware draft. Sparse data do not support positive complementarity, probability calibration or population transfer claims. See `task_traceability.csv` for T12.1-T12.11 and `docs/reproducibility/STAGE12_REPRODUCTION.md` for commands.
"""
    (reports / "STAGE12_REPORT.md").write_text(text, encoding="utf-8")
    files = [seal(root, output / "development_run.json")]
    if transfer:
        files.append(seal(root, output / "transfer_run.json"))
    files += [seal(root, reports / n) for n in ("G12_ACCEPTANCE.json", "TESS_SCOPE_DECISION.json", "recalibration_note.json", "task_traceability.csv", "MODEL_CARD.md", "STAGE12_REPORT.md")]
    build_paper(root, cfg, gate, primary)
    files += [seal(root, root / "paper3" / name) for name in ("main.tex", "results_status.tex", "results_tables.tex", "references.bib")]
    if (reports / "figure_manifest.json").exists():
        figure_manifest = read_json(reports / "figure_manifest.json")
        files.append(seal(root, reports / "figure_manifest.json"))
        for figure in figure_manifest["figures"]:
            files.extend(figure["files"] + figure["sources"])
    write_json(reports / "evidence_manifest.json", {"schema_version": 1, "files": files})
    return gate


def build_paper(root: Path, cfg: dict[str, Any], gate: dict[str, Any], primary: list[dict[str, Any]]) -> None:
    paper = root / "paper3"
    paper.mkdir(exist_ok=True)
    status = gate["status"].replace("_", r"\_")
    macros = f"\\newcommand{{\\GateStatus}}{{{status}}}\n\\newcommand{{\\DevelopmentStars}}{{{gate['usable_development_stars']}}}\n\\newcommand{{\\TessSectors}}{{{gate['actual_TESS_sectors']}}}\n"
    (paper / "results_status.tex").write_text(macros, encoding="utf-8")
    lines = [r"\begin{tabular}{lrrrr}", r"Quantity & Stars & Baseline MAE & Hybrid MAE & Improvement \\", r"\hline"]
    for row in primary:
        def number(value: Any) -> str:
            return f"{value:.5f}" if value is not None else "--"
        lines.append(f"{row['quantity']} & {row['paired_stars']} & {number(row['metrics']['baseline']['fractional_MAE'])} & {number(row['metrics']['hybrid']['fractional_MAE'])} & {number(row['mean_fractional_loss_improvement'])} " + r"\\")
    lines.append(r"\end{tabular}")
    (paper / "results_tables.tex").write_text("\n".join(lines) + "\n", encoding="utf-8")
    source = r"""\documentclass[11pt]{article}
\usepackage[margin=25mm]{geometry}
\usepackage{amsmath,booktabs,graphicx,hyperref}
\input{results_status}
\title{Conditional utility and transfer limits of topological asteroseismic descriptors}
\author{Gabriel Wendell}
\date{Stage 12 working draft}
\begin{document}\maketitle
\begin{abstract}
We implement a grouped comparison of compact classical and hybrid seismic models,
physical Kepler-to-TESS degradation and frozen-method quality screening. The current
dataset supports \DevelopmentStars{} usable development stars; \TessSectors{} actual
Rudy TESS sectors supply a descriptive transfer case. Scientific G12 is
\GateStatus. No positive population increment, calibrated detection or population
transfer claim follows from this implementation snapshot.
\end{abstract}
\section{Question and controls}
The relevant practical question is whether a small collection of geometric
descriptors improves prediction after conventional seismic estimates and matched
controls are included. Path-superlevel $H_0$ persistence and peak prominence are
the same scalar information. Their location descriptor belongs in both models;
the baseline additionally includes a conventional graph-ridge score. Solar-like
oscillation scaling and observational context follow standard reviews
\cite{ChaplinMiglio2013,GarciaBallot2019}. The hybrid
adds a nominal comb score, the excess competing-alias score and a cylindrical
geometry descriptor. A gain within a compact regression class would establish
conditional operational utility, not independent spectral information.
The observations and published reference centers follow the LEGACY studies
\cite{Lund2017,SilvaAguirre2017,Lund2017Erratum}.
\section{Population and prediction tasks}
The existing 39/13/13 development/internal/final partition is retained, with Rudy
outside model fitting. Features are extracted without reference values;
published centers enter only supervised targets and evaluation. Missing inputs
and pipeline failures retain their cohort rows. Global parameter regression is
the primary task. Catastrophic conventional-estimator failure and nominal-alias
reliability are binary quality tasks when class support permits. The selected
positive-only population cannot calibrate astrophysical signal absence.
\section{Models and grouped validation}
For quantity $q$, the target is $y_i=\log(q_i^{\rm ref}/q_i^{\rm classical})$.
The fitted correction is $\widehat q_i=q_i^{\rm classical}\exp(\beta_0+x_i^T\beta)$.
Ridge parameters minimize
\[\sum_i w_i(y_i-\beta_0-x_i^T\beta)^2+\lambda\|\beta\|^2,\]
where each parent star has total weight one. Median imputation and standardization
are fitted inside training folds. Three deterministic outer star folds and three
inner star folds isolate penalty selection from out-of-sample prediction.
The registered grid is $\lambda\in\{1,10,100\}$. Logistic quality models use the
same grouped design; an inner-OOF logit layer calibrates probabilities without
outer test outcomes. Unsupported class/fold fits are withheld.
\section{Uncertainty and practical utility}
The primary loss is absolute fractional error. The paired increment is
$d_i=|\widehat q_i^{B}/q_i^{\rm ref}-1|-|\widehat q_i^{H}/q_i^{\rm ref}-1|$.
Prespecified practical margins are 0.01 for $\nu_{\max}$ and 0.005 for
$\Delta\nu$. Superiority and two-one-sided equivalence tests receive separate
three-test superiority and separate two-regression equivalence corrections. Paired star bootstrap intervals are conditional
on the fitted OOF models; full fitting-selection uncertainty is not represented.
Empirical intervals use inner OOF residual ranks. They are not exact conformal
intervals, and insufficient rank support produces a missing interval. Coverage
uses published reference centers rather than known stellar truth. Quality-model
Brier scores, fixed-bin calibration and threshold decision curves are reported
only with both outcome classes. TESS risk probabilities are withheld under
mission shift. A quality flag is not an oscillation detection.
\section{Current grouped evidence}
\input{results_tables}
\par\medskip
These development OOF measurements are a sparse pilot. Unusable stars are not
imputed as successful observations. The source archive includes inherited
pipeline failures; their reasons and compatibility repairs are preserved. The
registered minimum of 20 development stars is a claim-support guard, not a
formal assertion of statistical power. A signed model release must precede the
original Stage 11 holdout opening, after which the first archive is applied once.
\IfFileExists{../figures/stage12/stage12_oof_increment.pdf}{%
\begin{figure}[ht]\centering
\includegraphics[width=\linewidth]{../figures/stage12/stage12_oof_increment.pdf}
\caption{Paired outer-fold errors and conditional bootstrap increments.
The sparse development pilot does not support population complementarity.}\end{figure}}{}
\section{Physical degradation and contribution trajectories}
Kepler Q5 samples are integrated as a piecewise-linear flux curve over target
exposures. Unsupported exposures and long source gaps are rejected. Cadence,
available duration, noise, real sector masks, extra duty loss and contamination
are changed along registered trajectories. Seeds depend on parent star, sector,
source offset and draw; paired methods and degradation levels share random
numbers. Every generated time/flux array and analysis checkpoint is archived.
Contamination dilutes variability before instrumental noise is added. Inherited
Kepler noise is retained. The unit color-response assumption is a sensitivity;
it does not constitute a measured Kepler/TESS passband conversion. The noise
model and real-window coverage remain explicit nuisance limitations.
\section{Actual Rudy sectors and combinations}
The frozen model digest is checked before and during sector processing. All 11
registered SPOC sectors are retained, including quality rejection and
nondetection cases. Actual sectors were previously inspected in Stage 10, so
this is a reproducible case study rather than new blinded test data. Registered
adjacent combinations average PSDs incoherently with exposure weights; they do
not coherently stitch stellar phases across years. Candidate estimates are
retained separately from accepted measurements. Repeated sectors, offsets and
draws still describe one parent star. Conditional degradation quantiles are not
population confidence intervals.
\IfFileExists{../figures/stage12/stage12_transfer_trajectories.pdf}{%
\begin{figure}[ht]\centering
\includegraphics[width=\linewidth]{../figures/stage12/stage12_transfer_trajectories.pdf}
\caption{Rudy cumulative degradation trajectories. Rejected candidates remain
visible; recoverability additionally requires quality acceptance.}\end{figure}}{}
\section{Recalibration, scope and counterexamples}
A separately authorized layer may estimate a star-weighted median log offset
using development simulations from non-Rudy stars. Holdout stars, Rudy and actual
test sectors are forbidden from calibration fitting. Features remain fixed, and
the calibration layer requires evaluation on disjoint simulation stars. No layer
is applied in this snapshot. Missing envelopes, competing aliases, source gaps,
out-of-range features, unavailable classes and mission shift are explicit failure
domains. The current scope decision stops at Rudy transfer limits; no powered
broader TESS sample is established.
\section{Reproducibility and claims}
The release supplies model JSON, feature/task registries, grouped fold audits,
paired results, source-backed figures, degraded light curves, quality reasons,
and a model card. Base inference requires NumPy/SciPy only; mission adapters use
the existing optional astronomy environment. G7's delay-topology drop and G8's
geometry-only interpretation are preserved. Population complementarity requires
locked out-of-sample improvement beyond a practical margin or supported failure
calibration; positive transfer requires compatible actual observations within
uncertainty. Until those conditions are supported, the honest output is a
validation-pending pilot and stated transfer limits.
\bibliographystyle{plain}\bibliography{references}
\end{document}
"""
    (paper / "main.tex").write_text(source, encoding="utf-8")
    (paper / "references.bib").write_text((root / "paper2/references.bib").read_text(), encoding="utf-8")
    (paper / "README.md").write_text("# Paper III draft\n\nGenerated from archived Stage 12 evidence. Compile: pdflatex main; bibtex main; pdflatex main; pdflatex main. Review and expand scientific discussion before publication.\n", encoding="utf-8")
