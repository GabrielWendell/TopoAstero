"""Synthetic end-to-end inference, transfer checkpoints and reporting."""
from __future__ import annotations

import copy

import numpy as np
import pytest
import yaml

from topoastero.config import content_hash
from topoastero.hybrid import pipeline, plotting, reporting, validation
from topoastero.hybrid.features import fingerprint
from topoastero.population_store import read_json, write_json, write_table


def test_development_reuses_exact_checkpoints_and_rejects_changes(hybrid_fitted: tuple) -> None:
    root, cfg, rows, _ = hybrid_fitted
    run = pipeline.run_development(root, cfg)
    pack = read_json(root / cfg["output"] / "models.json")
    assert run["usable_stars"] == 30 and len(pack["models"]) == 8
    assert pack["holdout_used"] is False and pack["unique_training_stars"] == len(rows)
    tasks = read_json(root / cfg["output"] / "probability_calibration.json")["tasks"]
    assert any(t["status"] == "withheld_positive_only_cohort" for t in tasks)
    (root / "synthetic_inputs.json").write_text("{}\n")
    with pytest.raises(ValueError, match="changed"):
        pipeline.run_development(root, cfg)
    write_json(root / cfg["release"], {"SYNTHETIC": True})
    with pytest.raises(ValueError, match="signed"):
        pipeline.run_development(root, cfg)


def test_insufficient_stars_and_fold_class_support_are_explicit(hybrid_repository: tuple, monkeypatch: pytest.MonkeyPatch) -> None:
    root, cfg, rows, ledger = hybrid_repository
    monkeypatch.setattr(pipeline, "load_dataset", lambda r, c: (rows[:3], ledger, []))
    run = pipeline.run_development(root, cfg)
    assert run["status"] == "insufficient_training_stars"
    assert read_json(root / cfg["output"] / "models.json")["models"] == {}
    cfg["output"] = "results/synthetic_fold_failure"
    monkeypatch.setattr(pipeline, "load_dataset", lambda r, c: (rows, ledger, []))
    original = pipeline.nested_predict
    def fail_binary(*args, **kwargs):
        if kwargs.get("binary"):
            raise ValueError("SYNTHETIC inner class shortage")
        return original(*args, **kwargs)
    monkeypatch.setattr(pipeline, "nested_predict", fail_binary)
    pipeline.run_development(root, cfg)
    tasks = read_json(root / cfg["output"] / "probability_calibration.json")["tasks"]
    assert sum(t["status"] == "withheld_fold_class_support" for t in tasks) == 4


def sample_analysis(rows: list[dict]) -> dict:
    row = rows[15]
    return {"features": copy.deepcopy(row["features"]), "classical_numax": row["classical"]["numax"],
            "classical_dnu": row["classical"]["dnu"], "envelope_ratio": 2., "maximum_alias_score": .4,
            "nominal_score": .5, "nominal_winner_at_boundary": False}


def test_qc_keeps_candidates_but_withholds_risk_under_mission_shift(hybrid_fitted: tuple) -> None:
    root, cfg, rows, _ = hybrid_fitted
    pack = read_json(root / cfg["output"] / "models.json")
    raw = sample_analysis(rows)
    kepler = pipeline.apply_models(raw, pack, cfg, mission="Kepler")
    assert all(r["failure_probability"] is not None and r["alias_unreliable_probability"] is not None for r in kepler)
    tess = pipeline.apply_models(raw, pack, cfg, mission="TESS")
    assert all(r["failure_probability"] is None and r["candidate_lower"] is None and r["candidate_estimate"] is not None for r in tess)
    weak = pipeline.apply_models({**raw, "envelope_ratio": 1}, pack, cfg, mission="TESS")
    assert all(not r["accepted"] and "missing_or_weak_envelope" in r["flags"] for r in weak)
    ambiguous = pipeline.apply_models({**raw, "maximum_alias_score": .8}, pack, cfg, mission="TESS")
    assert all(not r["accepted"] for r in ambiguous if r["quantity"] == "dnu")
    shifted = copy.deepcopy(raw)
    shifted["features"]["log_duration"] = 1e3
    assert all("domain_shift" in r["flags"] for r in pipeline.apply_models(shifted, pack, cfg, mission="TESS"))
    missing = pipeline.apply_models(raw, {"models": {}}, cfg, mission="TESS")
    assert all("model_unavailable" in r["flags"] and r["estimate"] is None for r in missing)
    excessive = copy.deepcopy(pack)
    for model in excessive["models"].values():
        if model["kind"] == "ridge":
            model["coefficients"][0] = 100
    assert all(r["candidate_estimate"] is None for r in pipeline.apply_models(raw, excessive, cfg, mission="Kepler"))


def run_fake_transfer(root, cfg, rows, monkeypatch):
    cfg["transfer"]["pilot_sectors"] = [14]
    cfg["transfer"]["offsets_days"] = [0.0]
    cfg["transfer"]["pilot_replicates"] = 1
    cfg["output"] = "results/synthetic_transfer"
    (root / "configs/stage12_hybrid.yaml").write_text(yaml.safe_dump(cfg))
    pipeline.run_development(root, cfg)
    source = np.arange(0., 3*86400, 30.)
    window = np.arange(0., 2*86400, 120.)/86400
    sectors = [{"sector": s, "time": window, "flux": np.sin(window), "cadence_seconds": 120.} for s in (14, 15, 40, 41, 54, 55, 74, 75, 80, 81, 82)]
    monkeypatch.setattr(pipeline, "read_mission_inputs", lambda *a: (source, np.sin(source/500), sectors, []))
    monkeypatch.setattr(pipeline, "white_floor", lambda *a: .1)
    write_table(root / "results/stage10/tess_sectors.csv", [{"sector": s["sector"], "white_psd": .2} for s in sectors])
    write_json(root / "results/stage10/benchmark_capsule.json", {"SYNTHETIC": True})
    monkeypatch.setattr(pipeline, "analyze_curve", lambda *a: (sample_analysis(rows), np.linspace(105, 3900, 500), np.ones(500)))
    import topoastero.population as population
    monkeypatch.setattr(population, "fit_population_background", lambda *a: (np.ones(500), {}))
    monkeypatch.setattr(population, "estimate_points", lambda *a: sample_analysis(rows))
    return pipeline.run_transfer(root, root / "data/raw", cfg)


def test_transfer_archive_counts_real_sectors_and_same_parent(hybrid_fitted: tuple, monkeypatch: pytest.MonkeyPatch) -> None:
    root, cfg, rows, _ = hybrid_fitted
    run = run_fake_transfer(root, cfg, rows, monkeypatch)
    assert run["cells"] == 8 and run["actual_sectors"] == 11 and run["parent_stars"] == 1
    cases = read_json(root / cfg["output"] / "actual_tess.json")
    assert len(cases["rows"]) == 44 and len(cases["combinations"]) == 4
    assert cases["actual_sectors_used_for_training"] is False
    assert pipeline.run_transfer(root, root / "data/raw", cfg) == run
    marker = root / cfg["output"] / "transfer_run.json"
    marker.unlink()
    assert pipeline.run_transfer(root, root / "data/raw", cfg)["files"] == run["files"]
    payload = root / next(r["path"] for r in run["files"] if r["path"].endswith(".npz"))
    payload.write_bytes(b"altered")
    with pytest.raises(ValueError, match="completed transfer"):
        pipeline.run_transfer(root, root / "data/raw", cfg)
    marker.unlink()
    with pytest.raises(ValueError, match="degradation checkpoint"):
        pipeline.run_transfer(root, root / "data/raw", cfg)


def test_pipeline_failure_rows_and_optional_calibration_are_archived(hybrid_fitted: tuple, monkeypatch: pytest.MonkeyPatch) -> None:
    root, cfg, rows, _ = hybrid_fitted
    run_fake_transfer(root, cfg, rows, monkeypatch)
    output = root / cfg["output"]
    for path in (output / "degraded").glob("*"):
        path.unlink()
    (output / "transfer_run.json").unlink()
    write_json(output / "authorized_calibration_layer.json", {"authorization": "SYNTHETIC", "offsets": {"baseline_numax": .01}})
    def fail(*a):
        raise ValueError("SYNTHETIC absent envelope")
    monkeypatch.setattr(pipeline, "analyze_curve", fail)
    run = pipeline.run_transfer(root, root / "data/raw", cfg)
    assert run["recalibration_applied"]
    failures = read_json(output / "actual_tess.json")["rows"]
    assert len(failures) == 44 and all("pipeline_failure" in r["flags"] for r in failures)
    gate = reporting.build_report(root, cfg)
    assert gate["status"] == "validation_pending" and not gate["positive_population_transfer_claim"]
    assert read_json(root / cfg["reports"] / "recalibration_note.json")["applied"]
    assert validation.validate(root, prior=False) == []
    fig = plotting.build_figures(root, cfg, formats=())
    assert len(fig["figures"]) == 4 and all(f["sources"] for f in fig["figures"])
    (output / "models.json").write_text("{}\n")
    assert validation.validate(root, prior=False)


def test_validation_missing_and_claim_guard(hybrid_fitted: tuple, monkeypatch: pytest.MonkeyPatch) -> None:
    root, cfg, rows, _ = hybrid_fitted
    assert validation.validate(root, prior=False)
    run_fake_transfer(root, cfg, rows, monkeypatch)
    reporting.build_report(root, cfg)
    assert validation.validate(root, prior=False) == []
    gate_path = root / cfg["reports"] / "G12_ACCEPTANCE.json"
    gate = read_json(gate_path)
    gate["publication_ready"] = True
    gate["positive_population_transfer_claim"] = True
    gate["usable_development_stars"] = 9
    gate["positive_complementarity_claim"] = True
    write_json(gate_path, gate)
    issues = validation.validate(root, prior=False)
    assert any("unsupported" in i for i in issues) and any("sparse" in i for i in issues)
    assert gate["code_sha256"] == fingerprint(root) and gate["configuration_sha256"] == content_hash(cfg)


def test_transfer_recalibration_cannot_change_kepler_primary_predictions(hybrid_fitted: tuple) -> None:
    root, cfg, rows, _ = hybrid_fitted
    pack = read_json(root / cfg["output"] / "models.json")
    raw = sample_analysis(rows)
    original_kepler = pipeline.apply_models(raw, pack, cfg, mission="Kepler")
    original_tess = pipeline.apply_models(raw, pack, cfg, mission="TESS")
    pack["calibration_layer"] = {"offsets": {f"{method}_{q}": .05 for method in ("baseline", "hybrid") for q in ("numax", "dnu")}}
    calibrated_kepler = pipeline.apply_models(raw, pack, cfg, mission="Kepler")
    calibrated_tess = pipeline.apply_models(raw, pack, cfg, mission="TESS")
    assert calibrated_kepler == original_kepler
    assert all(new["candidate_estimate"] / old["candidate_estimate"] == pytest.approx(np.exp(.05)) for new, old in zip(calibrated_tess, original_tess, strict=True))


def test_transfer_checkpoint_locks_noise_inputs_and_training_labels(hybrid_fitted: tuple, monkeypatch: pytest.MonkeyPatch) -> None:
    root, cfg, rows, _ = hybrid_fitted
    run_fake_transfer(root, cfg, rows, monkeypatch)
    path = root / "results/stage10/tess_sectors.csv"
    original = path.read_bytes()
    path.write_bytes(original+b"\n")
    with pytest.raises(ValueError, match="completed transfer checkpoint"):
        pipeline.run_transfer(root, root / "data/raw", cfg)
    path.write_bytes(original)
    (root / "synthetic_inputs.json").write_text("{}\n")
    with pytest.raises(ValueError, match="changed before transfer"):
        pipeline.run_transfer(root, root / "data/raw", cfg)
