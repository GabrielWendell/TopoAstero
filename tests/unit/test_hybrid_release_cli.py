"""Real detached signatures over synthetic fixtures, never the research holdout."""
from __future__ import annotations

import copy
import subprocess

import pytest

from topoastero.hybrid import cli, pipeline, release, reporting
from topoastero.population_store import read_json, seal, write_json, write_table


def key_file(tmp_path):
    path = tmp_path / "synthetic_private.pem"
    subprocess.run(["openssl", "genpkey", "-algorithm", "RSA", "-pkeyopt", "rsa_keygen_bits:2048", "-out", str(path)], capture_output=True, check=True)
    return path


def sign(root, cfg, key):
    return release.freeze(root, cfg, signing_key=key, supervisor="SYNTHETIC supervisor", data_steward="SYNTHETIC steward", container_digest="sha256:"+"0"*64)


def test_signed_models_reject_mutations_and_post_opening_freeze(hybrid_fitted: tuple, tmp_path) -> None:
    root, cfg, _, _ = hybrid_fitted
    key = key_file(tmp_path)
    signed = sign(root, cfg, key)
    assert release.signature_valid(signed) and release.release_issues(root, cfg) == []
    malformed = copy.deepcopy(signed)
    malformed["signature_hex"] = "not hex"
    assert not release.signature_valid(malformed)
    altered = copy.deepcopy(signed)
    altered["payload"]["supervisor"] = "different"
    write_json(root / cfg["release"], altered)
    assert any("signature" in s for s in release.release_issues(root, cfg))
    write_json(root / cfg["release"], signed)
    source = root / "src/topoastero/hybrid/synthetic.py"
    source.write_text(source.read_text()+"# mutated\n")
    assert any("changed" in s for s in release.release_issues(root, cfg))
    with pytest.raises(ValueError):
        release.evaluate_confirmation(root, cfg)
    with pytest.raises(ValueError, match="cannot refreeze"):
        sign(root, cfg, key)
    assert not (root / cfg["confirmation_state"]).exists()


def test_signing_support_approval_key_and_prior_opening_guards(hybrid_fitted: tuple, tmp_path) -> None:
    root, cfg, _, _ = hybrid_fitted
    key = key_file(tmp_path)
    for kw in ({"supervisor": ""}, {"container_digest": "fake"}, {"signing_key": root / "uv.lock"}):
        args = {"signing_key": key, "supervisor": "SYNTHETIC", "data_steward": "SYNTHETIC", "container_digest": "sha256:"+"0"*64, **kw}
        with pytest.raises(ValueError):
            release.freeze(root, cfg, **args)
    path = root / cfg["output"] / "development_run.json"
    run = read_json(path)
    run["usable_stars"] = 9
    write_json(path, run)
    with pytest.raises(ValueError, match="supported"):
        sign(root, cfg, key)
    write_json(root / "registries/stage11_confirmation.json", {"SYNTHETIC": True})
    with pytest.raises(ValueError, match="BEFORE"):
        sign(root, cfg, key)
    assert release.release_issues(root, cfg) == ["missing or malformed Stage 12 release"]
    write_json(root / cfg["release"], {"payload": {}})
    assert release.release_issues(root, cfg) == ["malformed Stage 12 release"]


def test_confirmation_reserves_before_reading_and_applies_once(hybrid_fitted: tuple, tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    root, cfg, rows, ledger = hybrid_fitted
    sign(root, cfg, key_file(tmp_path))
    state11 = {"status": "completed", "opening_count": 1, "first_valid_run_preserved": True, "archive_manifest_sha256": "0"*64}
    write_json(root / "registries/stage11_confirmation.json", state11)
    monkeypatch.setattr(release, "validate_stage11", lambda *a, **k: [])
    calls = []
    final = [{**copy.deepcopy(r), "stable_star_id": f"KIC {4000000+i}", "role": "final_holdout"} for i, r in enumerate(rows[:13])]
    def load(*a, **kw):
        state = read_json(root / cfg["confirmation_state"])
        assert state["status"] == "running" and state["opening_count"] == 1
        assert kw == {"role": "final_holdout", "permit_confirmation": True}
        calls.append("reserved_first")
        return final, ledger[:13], [seal(root, root / "synthetic_inputs.json")]
    monkeypatch.setattr(release, "load_dataset", load)
    state = release.evaluate_confirmation(root, cfg)
    assert state["status"] == "completed" and state["first_valid_run_preserved"]
    assert calls == ["reserved_first"]
    result = read_json(root / cfg["output"] / "confirmation_increment.json")
    assert result["rows"][0]["paired_stars"] == 13 and len(result["quality_tasks"]) == 2
    assert result["rows"][0]["metrics"]["baseline"]["interval_available"] == 13
    with pytest.raises(ValueError, match="never rerun"):
        release.evaluate_confirmation(root, cfg)
    assert calls == ["reserved_first"]


def test_invalid_upstream_and_interrupted_confirmation_stay_closed(hybrid_fitted: tuple, tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    root, cfg, _, _ = hybrid_fitted
    sign(root, cfg, key_file(tmp_path))
    write_json(root / "registries/stage11_confirmation.json", {"status": "running", "opening_count": 1, "first_valid_run_preserved": False})
    with pytest.raises(ValueError, match="first confirmation"):
        release.evaluate_confirmation(root, cfg)
    write_json(root / "registries/stage11_confirmation.json", {"status": "completed", "opening_count": 1, "first_valid_run_preserved": True, "archive_manifest_sha256": "0"*64})
    monkeypatch.setattr(release, "validate_stage11", lambda *a, **k: ["SYNTHETIC stale archive"])
    with pytest.raises(ValueError, match="failed validation"):
        release.evaluate_confirmation(root, cfg)
    monkeypatch.setattr(release, "validate_stage11", lambda *a, **k: [])
    def fail(*a, **k):
        raise ValueError("SYNTHETIC interruption")
    monkeypatch.setattr(release, "load_dataset", fail)
    with pytest.raises(ValueError, match="interruption"):
        release.evaluate_confirmation(root, cfg)
    assert read_json(root / cfg["confirmation_state"])["status"] == "running"
    with pytest.raises(ValueError, match="never rerun"):
        release.evaluate_confirmation(root, cfg)


def test_cli_fit_report_validation_and_errors(hybrid_fitted: tuple, monkeypatch: pytest.MonkeyPatch, capsys) -> None:
    root, cfg, _, _ = hybrid_fitted
    prefix = ["--root", str(root)]
    assert cli.main([*prefix, "fit"]) == 0
    assert cli.main([*prefix, "report"]) == 0
    assert cli.main([*prefix, "validate", "--without-prior-stages"]) == 1
    monkeypatch.setattr(cli, "validate", lambda *a, **k: [])
    assert cli.main([*prefix, "validate", "--without-prior-stages"]) == 0
    monkeypatch.setattr(cli, "run_transfer", lambda *a: {"cells": 8, "actual_sectors": 11, "parent_stars": 1})
    assert cli.main([*prefix, "transfer", "--cache-dir", str(root)]) == 0
    monkeypatch.setattr(cli, "freeze", lambda *a, **k: {})
    assert cli.main([*prefix, "freeze", "--signing-key", str(root / "fake.pem"), "--supervisor", "SYNTHETIC", "--data-steward", "SYNTHETIC", "--container-digest", "fake"]) == 0
    monkeypatch.setattr(cli, "evaluate_confirmation", lambda *a: {"status": "SYNTHETIC"})
    assert cli.main([*prefix, "evaluate-confirmation"]) == 0
    monkeypatch.setattr(cli, "run_development", lambda *a: (_ for _ in ()).throw(ValueError("SYNTHETIC error")))
    assert cli.main([*prefix, "fit"]) == 1
    assert "SYNTHETIC error" in capsys.readouterr().out
    assert cfg["training_role"] == "development" and pipeline is not None and reporting is not None


def test_recalibration_cli_verifies_original_partition_and_exclusivity(hybrid_fitted: tuple) -> None:
    root, cfg, _, _ = hybrid_fitted
    prefix = ["--root", str(root)]
    ids = [f"KIC {5000000+i}" for i in range(10)]
    write_table(root / "registries/population_partitions.csv", [{"stable_star_id": s, "role": "development"} for s in ids])
    rows = [{"stable_star_id": s, "role": "development", "origin": "degradation_simulation", "method": m,
             "quantity": q, "estimate": 100., "reference": 101.} for s in ids for m in ("baseline", "hybrid") for q in ("numax", "dnu")]
    source = root / "synthetic_simulations.json"
    write_json(source, {"rows": rows})
    args = [*prefix, "recalibrate", "--simulations", str(source), "--authorization", "SYNTHETIC"]
    assert cli.main(args) == 0
    assert cli.main(args) == 1
    write_json(root / cfg["release"], {"SYNTHETIC": True})
    assert cli.main(args) == 1
    (root / cfg["release"]).unlink()
    rows[0]["stable_star_id"] = "KIC 9999999"
    write_json(source, {"rows": rows})
    assert cli.main(args) == 1
