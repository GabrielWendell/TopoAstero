"""Synthetic release fixtures test guards; they never open the research holdout."""

from __future__ import annotations

import copy
import json
import shutil
import subprocess
from pathlib import Path

import pytest

import topoastero.population_freeze as freeze
from topoastero.config import content_hash
from topoastero.population_acquisition import acquire_population, load_config
from topoastero.population_pipeline import cohort, run_role, run_star, source_fingerprint
from topoastero.population_store import (
    contained,
    read_json,
    seal,
    star_slug,
    write_json,
    write_table,
)

ROOT = Path(__file__).parents[2]


@pytest.fixture
def synthetic_repository(tmp_path: Path) -> tuple[Path, Path, dict, Path]:
    root = tmp_path / "fixture"
    cache = tmp_path / "cache"
    for path in ("configs/stage11_legacy.yaml", "registries/population_partitions.csv", "registries/split_attestation.json",
                 "registries/stage11_exclusions.csv", "registries/stage11_qa.jsonl", "data/reference/stellar_references.csv",
                 "evidence/benchmarks/legacy_population.csv", "environment/stage11.Dockerfile", "pyproject.toml", "uv.lock",
                 "reports/stage10/freeze_manifest.json", "docs/protocols/STAGE11_POPULATION_PROTOCOL.md"):
        dest = root / path
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / path, dest)
    (root / "paper1").mkdir()
    shutil.copyfile(ROOT / "paper1/references.bib", root / "paper1/references.bib")
    shutil.copytree(ROOT / "data/reference/stage11", root / "data/reference/stage11")
    (root / "src/topoastero").mkdir(parents=True)
    (root / "src/topoastero/fixture.py").write_text("# SYNTHETIC test source\n")
    (root / "workflows").mkdir()
    cfg = load_config(root)
    rows = []
    import csv

    for member in csv.DictReader((root / cfg["partitions"]).open()):
        for index in range(3):
            name = member["kic"] + f"-{index}.fits"
            path = cache / "kepler" / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b"SYNTHETIC_PAYLOAD_NOT_OBSERVATIONAL_DATA")
            rows.append({"product_key": name, "stable_star_id": member["stable_star_id"], "partition_role": member["role"],
                         "product_filename": name, "size_bytes": path.stat().st_size, "data_uri": "mast:SYNTHETIC", "payload_sha256": ""})
    write_table(root / cfg["products"], rows)
    acquire_population(root, cache, cfg)
    members = cohort(root, cfg)
    for role in ("development", "internal_validation"):
        directory = root / cfg["output"] / role
        selected = [m for m in members if m["role"] == role]
        write_json(directory / "summary.json", {"role": role, "holdout_used": False, "configuration_sha256": content_hash(cfg),
                                               "code_sha256": source_fingerprint(root), "stars": len(selected),
                                               "statuses": [{"stable_star_id": m["stable_star_id"], "status": "ok", "flags": []} for m in selected]})
        write_json(directory / "catalog.json", {"rows": [{"stable_star_id": m["stable_star_id"], "role": role, "method": method, "quantity": quantity}
                                                         for m in selected for method in ("classical", "topology") for quantity in ("numax", "dnu")]})
        write_json(directory / "run_manifest.json", {"files": [seal(root, directory / "summary.json"), seal(root, directory / "catalog.json")]})
    key = tmp_path / "fixture_private.pem"
    subprocess.run(["openssl", "genpkey", "-algorithm", "RSA", "-pkeyopt", "rsa_keygen_bits:2048", "-out", str(key)],
                   check=True, capture_output=True)
    return root, cache, cfg, key


def sign_fixture(fixture: tuple[Path, Path, dict, Path]) -> dict:
    root, cache, cfg, key = fixture
    return freeze.freeze_release(root, cache, cfg, supervisor="SYNTHETIC test supervisor", data_steward="SYNTHETIC test steward",
                                 container_digest="sha256:" + "0" * 64, signing_key=key)


def test_signed_exact_release_rejects_mutation_and_reopening(synthetic_repository: tuple, monkeypatch: pytest.MonkeyPatch) -> None:
    root, cache, cfg, _ = synthetic_repository
    release = sign_fixture(synthetic_repository)
    assert freeze.release_issues(root, cfg, release) == []
    modified = copy.deepcopy(release)
    modified["payload"]["supervisor"] = "changed"
    assert any("signature" in r for r in freeze.release_issues(root, cfg, modified))
    source = root / "src/topoastero/fixture.py"
    original = source.read_bytes()
    source.write_bytes(original + b"# change\n")
    with pytest.raises(ValueError, match=r"changed|stale"):
        freeze.open_confirmation(root, cache, cfg)
    assert not (root / cfg["confirmation_state"]).exists()
    source.write_bytes(original)
    calls = []

    def successful_run(repository: Path, _cache: Path, _cfg: dict, role: str, directory: Path, *, confirmation: bool) -> dict:
        calls.append(role)
        assert confirmation and role == "final_holdout"
        write_json(directory / "run_manifest.json", {"fixture": "SYNTHETIC", "files": []})
        return {"stars": 13, "stars_with_estimates": 13}

    monkeypatch.setattr(freeze, "run_role", successful_run)
    freeze.open_confirmation(root, cache, cfg)
    state = read_json(root / cfg["confirmation_state"])
    assert state["opening_count"] == 1 and state["first_valid_run_preserved"]
    with pytest.raises((ValueError, FileExistsError)):
        freeze.open_confirmation(root, cache, cfg)
    with pytest.raises(ValueError, match="interrupted"):
        freeze.open_confirmation(root, cache, cfg, resume=True)
    assert calls == ["final_holdout"]
    with pytest.raises(ValueError, match="already"):
        sign_fixture(synthetic_repository)
    with pytest.raises(ValueError, match="frozen"):
        acquire_population(root, cache, cfg)


def test_interruption_resumes_same_attempt(synthetic_repository: tuple, monkeypatch: pytest.MonkeyPatch) -> None:
    root, cache, cfg, _ = synthetic_repository
    sign_fixture(synthetic_repository)
    calls = []

    def interrupted(repository: Path, _cache: Path, _cfg: dict, role: str, directory: Path, *, confirmation: bool) -> dict:
        calls.append(role)
        if len(calls) == 1:
            raise RuntimeError("synthetic process interruption")
        write_json(directory / "run_manifest.json", {"files": [], "fixture": "SYNTHETIC"})
        return {"stars_with_estimates": 13}

    monkeypatch.setattr(freeze, "run_role", interrupted)
    with pytest.raises(RuntimeError, match="interruption"):
        freeze.open_confirmation(root, cache, cfg)
    state = read_json(root / cfg["confirmation_state"])
    assert state["status"] == "running" and state["opening_count"] == 1
    freeze.open_confirmation(root, cache, cfg, resume=True)
    assert read_json(root / cfg["confirmation_state"])["opening_count"] == 1


def test_payload_changes_fail_before_opening(synthetic_repository: tuple) -> None:
    root, cache, cfg, _ = synthetic_repository
    sign_fixture(synthetic_repository)
    manifest = read_json(root / cfg["acquisition"])
    row = next(r for r in manifest["products"] if r["role"] == "final_holdout")
    path = contained(cache, row["cache_relative_path"])
    path.write_bytes(b"X" * path.stat().st_size)
    with pytest.raises(ValueError, match="payload changed"):
        freeze.open_confirmation(root, cache, cfg)
    assert not (root / cfg["confirmation_state"]).exists()


def test_incomplete_development_cannot_freeze(synthetic_repository: tuple) -> None:
    root, _, cfg, _ = synthetic_repository
    path = root / cfg["output"] / "development/summary.json"
    d = read_json(path)
    d["statuses"][0]["status"] = "pipeline_failure"
    write_json(path, d)
    with pytest.raises(ValueError, match="finish acquisition"):
        sign_fixture(synthetic_repository)


def test_missing_inputs_do_not_open_holdout(synthetic_repository: tuple) -> None:
    root, _, cfg, _ = synthetic_repository
    member = next(m for m in cohort(root, cfg) if m["role"] == "development")
    missing_cache = root / "missing_cache"
    directory = root / "fixture_results" / star_slug(member["stable_star_id"])
    result = run_star(root, missing_cache, cfg, member, directory)
    assert result["status"] == "missing_input" and result["available_products"] == 0
    assert run_star(root, missing_cache, cfg, member, directory) == result
    with pytest.raises(ValueError, match="holdout"):
        run_role(root, missing_cache, cfg, "final_holdout", root / "holdout")
    with pytest.raises(ValueError, match="reserved"):
        run_role(root, missing_cache, cfg, "final_holdout", root / "holdout", confirmation=True)
    changed = copy.deepcopy(cfg)
    changed["master_seed"] += 1
    with pytest.raises(ValueError, match="checkpoint"):
        run_star(root, missing_cache, changed, member, directory)
    path = root / cfg["partitions"]
    path.write_text(path.read_text() + "\n")
    with pytest.raises(ValueError, match="split checksum"):
        cohort(root, cfg)


def test_acquisition_detects_old_hash_mismatch(synthetic_repository: tuple) -> None:
    root, cache, cfg, _ = synthetic_repository
    manifest = read_json(root / cfg["acquisition"])
    path = contained(cache, manifest["products"][0]["cache_relative_path"])
    path.write_bytes(b"Z" * path.stat().st_size)
    with pytest.raises(ValueError, match="checksum mismatch"):
        acquire_population(root, cache, cfg)


@pytest.mark.parametrize("path", ["../secrets", "/tmp/secrets", "C:\\secrets", "a/../../secrets"])
def test_unsafe_paths_are_rejected(tmp_path: Path, path: str) -> None:
    with pytest.raises(ValueError, match="unsafe"):
        contained(tmp_path, path)


def test_release_signature_is_not_a_hash_attestation() -> None:
    bad = {"payload": {}, "payload_sha256": content_hash({}), "signature_hex": "invalid", "public_key_pem": "invalid"}
    assert freeze.release_issues(ROOT, load_config(ROOT), bad)
    assert json.loads(json.dumps(bad))["payload"] == {}


def synthetic_reference_bundle(root: Path, cache: Path) -> None:
    """Tiny CDS-shaped fixture containing all identifiers, explicitly synthetic."""
    cache.mkdir()
    (cache / "ReadMe").write_text("SYNTHETIC fixture: erratum 2017 ApJ 850, 110\n")
    mode_rows, ratio_rows, covariates = [], [], []
    for row in cohort(root, load_config(root)):
        kic = row["kic"]
        mode_rows.append(f"{kic:<8} {12:2d} 0 {1400.0:10.5f} {0.3:7.5f} {0.4:7.5f}".ljust(96))
        ratio_rows.append(f"{kic} r_02_ 12 0.07500 0.00300 0.00400")
        covariates.append(f"{kic}|Synthetic|8.5|2000|100|1|Simple")
    (cache / "table6.dat").write_text("\n".join([*mode_rows, mode_rows[0]]) + "\n")
    (cache / "table7.dat").write_text("\n".join(ratio_rows) + "\n")
    (cache / "table1.dat").write_text("\n".join(covariates) + "\n")


def test_reference_import_preserves_asymmetry_and_rejects_conflict(synthetic_repository: tuple, tmp_path: Path) -> None:
    from topoastero.population_references import import_references
    from topoastero.population_store import read_table

    root, _, _, _ = synthetic_repository
    cache = tmp_path / "references"
    synthetic_reference_bundle(root, cache)
    manifest = import_references(root, cache)
    assert manifest["stars"] == 66 and manifest["identical_duplicate_mode_rows"] == 1
    rows = read_table(root / "data/reference/stage11/mode_frequencies.csv")
    assert len(rows) == 66 and float(rows[0]["uncertainty_minus_uHz"]) == .3 and float(rows[0]["uncertainty_plus_uHz"]) == .4
    p = cache / "table6.dat"
    data = p.read_text().splitlines()
    data[-1] = data[-1][:14] + f"{1500.0:10.5f}" + data[-1][24:]
    p.write_text("\n".join(data) + "\n")
    with pytest.raises(ValueError, match="conflicting duplicate"):
        import_references(root, cache)
    (cache / "ReadMe").write_text("uncorrected edition")
    with pytest.raises(ValueError, match="edition"):
        import_references(root, cache)


def test_development_cli_report_and_missingness_end_to_end(synthetic_repository: tuple, tmp_path: Path, capsys: pytest.CaptureFixture) -> None:
    from topoastero.population_cli import main
    from topoastero.population_store import read_table

    root, cache, cfg, key = synthetic_repository
    prefix = ["--root", str(root)]
    refs = tmp_path / "reference_cli"
    synthetic_reference_bundle(root, refs)
    main([*prefix, "references", "--cache-dir", str(refs)])
    main([*prefix, "acquire", "--cache-dir", str(cache)])
    main([*prefix, "cohort"])
    main([*prefix, "log-change", "--note", "SYNTHETIC regression: missing cache"])
    main([*prefix, "run-development", "--cache-dir", str(tmp_path / "absent_cache")])
    main([*prefix, "report"])
    gate = read_json(root / "reports/stage11/G11_ACCEPTANCE.json")
    assert gate["status"] == "population_pending" and gate["holdout_opening_count"] == 0
    catalog = read_json(root / cfg["output"] / "development/catalog.json")["rows"]
    assert len(catalog) == 39 * 4 and all(r["estimate"] is None for r in catalog)
    atlas = read_table(root / "reports/stage11/failure_atlas.csv")
    assert len(atlas) == 53
    assert not (root / cfg["confirmation_state"]).exists()
    assert "False" not in (root / "paper2/results_status.tex").read_text()
    with pytest.raises(SystemExit, match="missing Stage 11"):
        main([*prefix, "validate", "--without-prior-stages"])
    with pytest.raises(SystemExit, match="finish acquisition"):
        main([*prefix, "freeze", "--cache-dir", str(cache), "--supervisor", "SYNTHETIC", "--data-steward", "SYNTHETIC",
              "--container-digest", "sha256:" + "0" * 64, "--signing-key", str(key)])
    with pytest.raises(SystemExit):
        main([*prefix, "open-confirmation", "--cache-dir", str(cache)])
    with pytest.raises(SystemExit, match="may not tune"):
        main([*prefix, "log-change", "--note", "test", "--affected-roles", "final_holdout"])
    assert "no holdout" in capsys.readouterr().out


def test_completed_scientific_failure_is_never_retried(synthetic_repository: tuple, monkeypatch: pytest.MonkeyPatch) -> None:
    import topoastero.population_pipeline as pipeline

    root, cache, cfg, _ = synthetic_repository
    member = next(m for m in cohort(root, cfg) if m["role"] == "development")
    directory = root / "failure_checkpoint" / star_slug(member["stable_star_id"])
    calls = []

    def failure(*args: object) -> None:
        calls.append(1)
        raise ValueError("SYNTHETIC scientific failure")

    monkeypatch.setattr(pipeline, "monthly_spectra", failure)
    result = run_star(root, cache, cfg, member, directory)
    assert result["status"] == "pipeline_failure"
    assert run_star(root, cache, cfg, member, directory) == result
    assert calls == [1]


def test_portable_reproduction_cannot_hide_material_or_flag_changes(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.syspath_prepend(str(ROOT / "workflows"))
    from check_stage10_portable_reproduction import differences

    issues = []
    metrics = {"maximum_absolute_difference": 0.0, "maximum_relative_difference": 0.0}
    differences({"estimate": 100.0, "flag": "limited"}, {"estimate": 100.00001, "flag": "limited"}, "fixture", issues, metrics)
    assert issues == []
    differences({"estimate": 100.0, "flag": "limited"}, {"estimate": 100.1, "flag": "ok"}, "fixture", issues, metrics)
    assert any("numeric" in issue for issue in issues) and any("exact value" in issue for issue in issues)
