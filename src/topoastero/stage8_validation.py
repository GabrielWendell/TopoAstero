"""Independent offline integrity/decision validation for Stage 8 evidence."""

from __future__ import annotations

import csv
import json
import math
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from topoastero.config import configuration_hash, load_yaml
from topoastero.provenance import sha256_file
from topoastero.stage7_validation import validate_stage7

RUN_ID = "TA-S08-ECHELLE-R001"
METHODS = ("topology", "graph", "conventional", "hough", "acf", "psps")
SCHEMAS = (
    "echelle_score.schema.json", "cylindrical_pair.schema.json",
    "stage8_interval.schema.json", "stage8_gate.schema.json", "stage8_run_manifest.schema.json",
)
REQUIRED_FILES = (
    "configs/stage8_echelle.yaml", "registries/stage8_simulation_lock.yaml",
    "registries/stage8_decision_policy.yaml", "docs/science/CYLINDRICAL_ECHELLE_MATHEMATICS.md",
    "docs/protocols/STAGE8_ECHELLE_PROTOCOL.md", "notebooks/08_cylindrical_echelle.ipynb",
    "results/stage8/score_curves.csv", "results/stage8/paired_benchmark.csv",
    "results/stage8/null_maxima.csv", "results/stage8/intervals.csv",
    "results/stage8/bootstrap_draws.csv", "results/stage8/diagram_suite.json",
    "results/stage8/ratio_audit.csv", "results/stage8/failure_atlas.csv",
    "results/stage8/environment.json", "results/stage8/run_manifest.json",
    "reports/stage8/G8_ACCEPTANCE.json", "reports/stage8/STAGE8_REPORT.md",
    "reports/stage8/ALIAS_AND_ABLATION_REPORT.md",
    "reports/stage8/UNCERTAINTY_AND_FAILURE_ATLAS.md",
    "reports/stage8/RIDGE_ANGLES_AND_RATIO_AUDIT.md",
    "reports/stage8/TRACEABILITY_MATRIX.md", "reports/stage8/deliverable_manifest.csv",
    "reports/stage8/figures/paired_echelle.svg", "reports/stage8/figures/score_curves.svg",
    "reports/stage8/figures/paired_method_accuracy.svg",
    "reports/stage8/figures/interval_coverage.svg",
    "reports/stage8/figures/published_ratio_formula_audit.svg",
    "src/topoastero/echelle_topology.py", "src/topoastero/stage8_validation.py",
    "workflows/run_stage8_echelle.py", "workflows/validate_stage8.py",
    "workflows/build_stage8_manifest.py", "workflows/execute_stage8_notebook.py",
    "tests/unit/test_echelle_topology.py",
    "tests/governance/test_stage8_contract.py", "tests/governance/test_stage8_schemas.py",
    "tests/integration/test_stage8_cli.py",
)


def _csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _json(path: Path) -> dict[str, Any]:
    value: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    return value


def _near(left: float, right: float, *, tolerance: float = 2e-7) -> bool:
    return math.isfinite(left) and math.isfinite(right) and math.isclose(left, right, abs_tol=tolerance, rel_tol=tolerance)


def _record_seals(root: Path, records: list[dict[str, Any]], label: str, errors: list[str]) -> None:
    for record in records:
        relative = record.get("path", "")
        if not isinstance(relative, str) or "\\" in relative or relative.startswith("/") or ".." in Path(relative).parts:
            errors.append(f"invalid {label} path: {relative}")
            continue
        target = root / relative
        if not target.is_file() or record.get("sha256") != sha256_file(target) or (
            "size_bytes" in record and record["size_bytes"] != target.stat().st_size
        ):
            errors.append(f"stale {label} seal: {relative}")


def validate_stage8(root: str | Path, *, require_prior_stages: bool = True) -> list[str]:
    """Check frozen geometry, paired evidence, uncertainty, G8 and byte provenance."""

    repository = Path(root).resolve()
    errors = [f"missing required Stage 8 file: {path}" for path in REQUIRED_FILES if not (repository / path).is_file()]
    errors.extend(f"missing Stage 8 schema: {name}" for name in SCHEMAS if not (repository / "schemas" / name).is_file())
    if errors:
        return errors
    config = load_yaml(repository / "configs/stage8_echelle.yaml")
    policy = load_yaml(repository / "registries/stage8_decision_policy.yaml")
    lock = load_yaml(repository / "registries/stage8_simulation_lock.yaml")
    if config.get("config_id") != "TA-STAGE8-ECHELLE-1.0" or config.get("run_id") != RUN_ID or config.get("software_version") != "TopoAstero-0.9.0":
        errors.append("Stage 8 frozen config identity/version drifted")
    scope = config.get("scope", {})
    if scope.get("expected_cells") != 24 or scope.get("calibration") != "odd_cell_number" or scope.get("evaluation") != "even_cell_number" or scope.get("population_spectra_allowed") is not False or scope.get("final_holdout_allowed") is not False:
        errors.append("Stage 8 simulation split or forbidden-data boundary drifted")
    geometry = config.get("geometry", {})
    if geometry.get("periodic_axis") != "angular_only" or geometry.get("cubical_filtration") != "upper_star_minimum_vertex_F2" or geometry.get("incomplete_order_rule") != "omit_vertices_and_incident_cells":
        errors.append("Stage 8 cylindrical filtration contract drifted")
    if policy.get("status") != "locked_before_stage8_execution" or policy.get("decision_rule") != "retain_topology_only_if_all_three_utility_thresholds_pass_else_geometry_only":
        errors.append("Stage 8 decision policy is not frozen")
    if lock.get("status") != "locked_before_stage8_execution" or lock.get("expected_cells") != 24:
        errors.append("Stage 8 input lock is invalid")
    if len(lock.get("sealed_inputs", [])) != 6 or lock.get("split", {}).get("overlap_allowed") is not False:
        errors.append("Stage 8 input/split lock is incomplete")
    _record_seals(repository, lock.get("sealed_inputs", []), "input lock", errors)
    for name in SCHEMAS:
        schema = _json(repository / "schemas" / name)
        if schema.get("$schema") != "https://json-schema.org/draft/2020-12/schema" or schema.get("additionalProperties") is not False:
            errors.append(f"invalid or open Stage 8 schema: {name}")

    scores = _csv(repository / "results/stage8/score_curves.csv")
    benchmark = _csv(repository / "results/stage8/paired_benchmark.csv")
    nulls = _csv(repository / "results/stage8/null_maxima.csv")
    intervals = _csv(repository / "results/stage8/intervals.csv")
    boot = _csv(repository / "results/stage8/bootstrap_draws.csv")
    ratios = _csv(repository / "results/stage8/ratio_audit.csv")
    stress = _csv(repository / "results/stage8/failure_atlas.csv")
    evaluation_ids = {f"F4-{number:03d}" for number in range(2, 25, 2)}
    all_ids = {f"F4-{number:03d}" for number in range(1, 25)}
    score_by_cell: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in scores:
        score_by_cell[row["cell_id"]].append(row)
        if row["role"] != ("evaluation" if row["cell_id"] in evaluation_ids else "calibration"):
            errors.append(f"score role drifted: {row['cell_id']}")
        if not _near(float(row["topology_score"]), 0.55 * float(row["finite_h0_component"]) + 0.45 * float(row["graph_score"])):
            errors.append(f"frozen score equation drifted: {row['cell_id']}")
        if int(row["valid_orders"]) < 4 and any(abs(float(row[f"{method}_score"])) > 1e-12 for method in METHODS):
            errors.append(f"incomplete order accepted for inference: {row['cell_id']}")
    if len(scores) != 360 or set(score_by_cell) != all_ids or any({int(row["trial_index"]) for row in rows} != set(range(15)) or len(rows) != 15 for rows in score_by_cell.values()):
        errors.append("score grid must cover exactly 15 trials x 24 cells")
    prior = {row["cell_id"]: float(row["best_trial_uHz"]) for row in _csv(repository / "results/stage6/comb_benchmark.csv") if row["method"] == "acf"}
    design = {row["cell_id"]: row for row in _csv(repository / "registries/stage4_factorial_design.csv")[:24]}
    for cell, rows in score_by_cell.items():
        for row in rows:
            index = int(row["trial_index"])
            alias = ("half", "nominal", "double")[index // 5]
            expected = prior[cell] * (0.5, 1.0, 2.0)[index // 5] * (0.9, 0.95, 1.0, 1.05, 1.1)[index % 5]
            if row["alias"] != alias or not _near(float(row["spacing_uHz"]), expected):
                errors.append(f"Stage 6 non-truth prior/trial grid drifted: {cell}/{index}")
    bench_by_key = {(row["cell_id"], row["method"]): row for row in benchmark}
    if len(benchmark) != 144 or len(bench_by_key) != 144 or set(bench_by_key) != {(cell, method) for cell in all_ids for method in METHODS}:
        errors.append("six paired methods must cover all 24 cells")
    for (cell, method), row in bench_by_key.items():
        if row["role"] != ("evaluation" if cell in evaluation_ids else "calibration"):
            errors.append(f"benchmark role drifted: {cell}")
        ordered = sorted(score_by_cell[cell], key=lambda item: int(item["trial_index"]))
        winner = max(ordered, key=lambda item: (float(item[f"{method}_score"]), -int(item["trial_index"])))
        truth = float(row["true_dnu_uHz"])
        selected = float(row["selected_dnu_uHz"])
        correct = abs(selected - truth) / truth <= 0.12
        design_factor = design[cell]
        nyquist = 1e6 / (2 * float(design_factor["cadence_seconds"]))
        expected_detectable = (
            design_factor["snr_level"] in {"Medium", "High"}
            and int(design_factor["visible_orders"]) >= 9
            and float(design_factor["duty_cycle"]) >= 0.8
            and nyquist > float(design_factor["numax_uHz"]) + 1.5 * float(design_factor["dnu_uHz"])
        )
        if not _near(truth, float(design_factor["dnu_uHz"])) or not _near(float(row["stage6_acf_anchor_uHz"]), prior[cell]) or row["detectable"] != str(expected_detectable).lower():
            errors.append(f"sealed truth/ACF prior/eligibility drifted: {cell}/{method}")
        if row["selected_alias"] != winner["alias"] or not _near(selected, float(winner["spacing_uHz"])) or row["correct"] != str(correct).lower() or not _near(float(row["relative_error"]), abs(selected - truth) / truth):
            errors.append(f"paired argmax/accuracy drifted: {cell}/{method}")
        offered = any(abs(float(item["spacing_uHz"]) - truth) / truth <= 0.12 for item in ordered)
        if row["true_spacing_in_grid"] != str(offered).lower():
            errors.append(f"truth-in-grid audit drifted: {cell}/{method}")
    if len(nulls) != 288 or Counter(row["cell_id"] for row in nulls) != Counter({cell: 24 for cell in evaluation_ids}):
        errors.append("independent max-statistic null table is incomplete")
    for cell in evaluation_ids:
        rows = [row for row in nulls if row["cell_id"] == cell]
        if {int(row["draw"]) for row in rows} != set(range(1, 25)) or any(row["trial_count"] != "15" or row["null_family"] != "background_only_matched_gamma_periodogram" or row["seed_stream"] != "observed_seed_plus_81000" for row in rows):
            errors.append(f"null family/trial maximum drifted: {cell}")
        observed = float(bench_by_key[(cell, "topology")]["score"])
        expected_p = (1 + sum(float(row["maximum_statistic"]) >= observed for row in rows)) / 25
        if not _near(float(bench_by_key[(cell, "topology")]["max_statistic_pvalue"]), expected_p):
            errors.append(f"maximum-statistic multiplicity correction drifted: {cell}")
    if any(row["max_statistic_pvalue"] for row in benchmark if row["role"] != "evaluation" or row["method"] != "topology"):
        errors.append("maximum-statistic p-value leaked to untested rows")

    if len(intervals) != 12 or {row["cell_id"] for row in intervals} != evaluation_ids or len(boot) != 96:
        errors.append("evaluation-only uncertainty refits are incomplete")
    for row in intervals:
        cell = row["cell_id"]
        true, point, lower, upper = (float(row[key]) for key in ("true_dnu_uHz", "point_dnu_uHz", "lower_dnu_uHz", "upper_dnu_uHz"))
        if not (lower <= point <= upper) or not _near(true, float(design[cell]["dnu_uHz"])) or row["covers_truth"] != str(lower <= true <= upper).lower() or row["replicates"] != "8" or not _near(float(row["interval_level"]), 0.9):
            errors.append(f"spacing interval contract drifted: {cell}")
        draws = [item for item in boot if item["cell_id"] == cell]
        if {int(item["draw"]) for item in draws} != set(range(1, 9)) or {item["branch"] for item in draws} != {"primary", "slope_minus", "slope_plus"} or int(row["ridge_draws_available"]) != sum(bool(item["leading_ridge_phase_cycles"]) for item in draws):
            errors.append(f"bootstrap/background/phase audit drifted: {cell}")
        if not _near(point, float(bench_by_key[(cell, "topology")]["selected_dnu_uHz"])):
            errors.append(f"interval point differs from paired benchmark: {cell}")
    suite = _json(repository / "results/stage8/diagram_suite.json")
    if suite.get("cell_id") != "F4-004" or suite.get("periodic_axes") != [False, True] or suite.get("coefficient_field") != "F2" or suite.get("essential_h1") != 1 or suite.get("rectangle_essential_h1") != 0:
        errors.append("exact cylinder/rectangle topology evidence is invalid")
    pairs = suite.get("pairs", [])
    if not pairs or not any(pair.get("dimension") == 1 and pair.get("essential") for pair in pairs):
        errors.append("localized cylindrical H1 diagram is missing")
    if any((pair.get("death") is None) != bool(pair.get("essential")) for pair in pairs):
        errors.append("essential persistence pair has inconsistent death")
    published = [row for row in ratios if row["source"] == "Lund2017_Table6_v_Table7"]
    if {row["ratio"] for row in published} != {"r02", "r01", "r10"} or max(float(row["uncertainty_normalized_difference"]) for row in published) > 1:
        errors.append("published identified-mode ratio formula audit failed")
    if len(stress) != 24 or {row["factor"] for row in stress} != {"glitch", "curvature", "dropout", "avoided_crossing", "rotation", "noise"}:
        errors.append("six-factor stress atlas is incomplete")
    for factor in {row["factor"] for row in stress}:
        if {row["method"] for row in stress if row["factor"] == factor} != {"topology", "graph", "acf", "psps"}:
            errors.append(f"stress comparison is not paired: {factor}")

    detectable = {cell for cell in evaluation_ids if bench_by_key[(cell, "topology")]["detectable"] == "true"}
    if not detectable or any(bench_by_key[(cell, method)]["detectable"] != bench_by_key[(cell, "topology")]["detectable"] for cell in evaluation_ids for method in METHODS):
        errors.append("detectability gate differs between paired methods")
    accuracy = {method: sum(bench_by_key[(cell, method)]["correct"] == "true" for cell in detectable) / len(detectable) for method in METHODS}
    coverage = sum(row["covers_truth"] == "true" for row in intervals if row["cell_id"] in detectable) / len(detectable)
    thresholds = config["gate"]
    useful = accuracy["topology"] >= thresholds["minimum_detectable_alias_accuracy"] and coverage >= thresholds["minimum_detectable_90pct_interval_coverage"] and accuracy["topology"] - accuracy["graph"] >= thresholds["minimum_topology_accuracy_gain_over_graph"]
    decision = "retain" if useful else "geometry_only"
    gate = _json(repository / "reports/stage8/G8_ACCEPTANCE.json")
    if gate.get("gate") != "G8" or gate.get("status") != "pass" or gate.get("decision") != decision or gate.get("claim") != ("topological_echelle_simulation_utility" if useful else "correct_cylindrical_geometry_only") or gate.get("population_spectra_used") is not False or gate.get("final_holdout_used") is not False:
        errors.append("G8 decision or restricted claim contradicts frozen evidence")
    if gate.get("detectable_evaluation_cells") != len(detectable) or not all(_near(gate[key], value) for key, value in (("alias_accuracy_topology", accuracy["topology"]), ("alias_accuracy_graph", accuracy["graph"]), ("interval_coverage", coverage))):
        errors.append("G8 metrics disagree with paired evaluation rows")
    if any(item.get("status") == "fail" for item in gate.get("checks", [])):
        errors.append("G8 contains a failed integrity check")

    manifest = _json(repository / "results/stage8/run_manifest.json")
    if manifest.get("run_id") != RUN_ID or manifest.get("status") != "complete" or manifest.get("decision") != decision or manifest.get("config_sha256") != configuration_hash(repository / "configs/stage8_echelle.yaml") or manifest.get("style_id") != "TA-PLOT-1.0":
        errors.append("Stage 8 run manifest identity/config/decision seal drifted")
    if manifest.get("population_spectra_used") is not False or manifest.get("final_holdout_used") is not False:
        errors.append("Stage 8 run manifest indicates forbidden data access")
    for kind in ("inputs", "outputs"):
        _record_seals(repository, manifest.get(kind, []), f"run manifest {kind}", errors)
    for path in sorted((repository / "reports/stage8/figures").glob("*.svg")):
        source = path.read_text(encoding="utf-8")
        if "TA-PLOT-1.0" not in source or "Machine-readable source:" not in source or "TopoAstero-0.9.0" not in source:
            errors.append(f"figure lacks style/provenance metadata: {path.name}")
    if len(list((repository / "reports/stage8/figures").glob("*.svg"))) != 5:
        errors.append("Stage 8 must include five source-backed figures")
    notebook = _json(repository / "notebooks/08_cylindrical_echelle.ipynb")
    joined = " ".join("".join(cell.get("source", [])) for cell in notebook.get("cells", []))
    code = [cell for cell in notebook.get("cells", []) if cell.get("cell_type") == "code"]
    if notebook.get("nbformat") != 4 or RUN_ID not in joined or "results/stage8" not in joined or not code or any(cell.get("execution_count") is None or not cell.get("outputs") for cell in code):
        errors.append("Stage 8 notebook is not executed or detached from governed outputs")
    deliverables = _csv(repository / "reports/stage8/deliverable_manifest.csv")
    if {row["deliverable"] for row in deliverables} != {"D8.1", "D8.2", "D8.3", "D8.4", "G8", "software"}:
        errors.append("Stage 8 deliverable groups are incomplete")
    _record_seals(repository, [dict(row, size_bytes=int(row["size_bytes"])) for row in deliverables], "deliverable", errors)
    if require_prior_stages:
        errors.extend(f"Stage 0-7 regression: {item}" for item in validate_stage7(repository, require_prior_stages=True))
    return errors
