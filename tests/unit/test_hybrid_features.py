"""Feature/role contracts, reference isolation and input seal protection."""
from __future__ import annotations

import copy
import math

import numpy as np
import pytest
import yaml

from topoastero.hybrid import features
from topoastero.population_store import seal, star_slug, write_json
from topoastero.provenance import sha256_file


def analysis() -> dict:
    return {"classical_numax": 2200., "classical_dnu": 100., "topology_numax": 2205., "envelope_ratio": 2., "duration_days": 30.,
            "native_window_resolution_uHz": .4, "duty_cycle": .9, "prominence_max_absolute_difference": 0.,
            "nominal_score": .5, "maximum_alias_score": .4,
            "echelle_scan": [{"alias_family": "nominal", "spacing_uHz": 100., "graph_only": .4, "topology": .6}]}


def test_features_are_label_free_and_prominence_matched() -> None:
    raw = analysis()
    expected = features.feature_row(raw)
    assert expected["prominence_delta"] == pytest.approx(math.log(2205/2200))
    assert set(expected) == set(features.CLASSICAL + features.TOPOLOGY)
    raw.update({"published_numax": 9e9, "published_dnu": 1e9, "individual_mode_labels": [0, 1]})
    assert features.feature_row(raw) == expected
    raw["prominence_max_absolute_difference"] = .1
    with pytest.raises(ValueError, match="prominence"):
        features.feature_row(raw)
    assert all(v is None for v in features.feature_row({}).values())
    raw = analysis()
    raw["echelle_scan"] = []
    assert features.feature_row(raw)["graph_score"] is None
    assert np.isnan(features.matrix([{"features": {}}], ["graph_score"])[0, 0])


@pytest.mark.parametrize("change", [
    {"training_role": "final_holdout"}, {"classical_features": ["published_numax"]}, {"outer_folds": 1},
    {"minimum_claim_stars": 9}, {"minimum_fit_stars": 3}, {"interval_level": 1},
    {"transfer": {"profile": "invalid"}}, {"transfer": {"recalibration_enabled": True}},
    {"transfer": {"source_quarter": 2}}, {"transfer": {"cadence_seconds": 30}},
    {"quality": {"probability_threshold": 1}},
])
def test_config_rejects_unlocked_and_nonphysical_changes(hybrid_repository: tuple, change: dict) -> None:
    root, cfg, _, _ = hybrid_repository
    altered = copy.deepcopy(cfg)
    for key, value in change.items():
        if isinstance(value, dict):
            altered[key].update(value)
        else:
            altered[key] = value
    (root / "configs/stage12_hybrid.yaml").write_text(yaml.safe_dump(altered))
    with pytest.raises(ValueError):
        features.load_config(root)


def test_dataset_keeps_failed_stars_and_seals_all_targets(hybrid_repository: tuple, monkeypatch: pytest.MonkeyPatch) -> None:
    root, cfg, _, _ = hybrid_repository
    members = [{"stable_star_id": f"KIC {3000000+i}", "role": "development", "numax_uHz": 2210., "dnu_uHz": 101.} for i in range(2)]
    monkeypatch.setattr(features, "cohort", lambda *a: members)
    for name in ("data/reference/stage11/reference_manifest.json", "data/reference/stage11/covariates.csv", "registries/stage11_exclusions.csv"):
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("SYNTHETIC input contract\n")
    directory = root / "results/synthetic/development"
    files = []
    for i, member in enumerate(members):
        raw = analysis() if i == 0 else {}
        raw.update({"stable_star_id": member["stable_star_id"], "role": "development", "reference_values_used_in_estimation": False,
                    "status": "SYNTHETIC" if i == 0 else "pipeline_failure", "reason": "SYNTHETIC gap"})
        path = directory / "stars" / star_slug(member["stable_star_id"]) / "analysis.json"
        write_json(path, raw)
        files.append(seal(root, path))
    write_json(directory / "run_manifest.json", {"files": files})
    write_json(root / cfg["stage11_evidence"], {"role_directories": {"development": "results/synthetic/development"}})
    rows, ledger, inputs = features.load_dataset(root, cfg)
    assert len(rows) == 1 and len(ledger) == 2 and ledger[1]["included"] is False
    assert any(i["path"] == "registries/population_partitions.csv" for i in inputs)
    assert any(i["path"].endswith("stellar_references.csv") for i in inputs)
    assert rows[0]["targets"]["numax"] == 2210
    path = root / files[0]["path"]
    path.write_text(path.read_text() + " ")
    with pytest.raises(ValueError, match="stale"):
        features.load_dataset(root, cfg)
    raw["stable_star_id"] = "KIC 9999999"
    write_json(path, raw)
    write_json(directory / "run_manifest.json", {"files": []})
    with pytest.raises(ValueError, match="leakage"):
        features.load_dataset(root, cfg)


def test_final_features_require_exact_reserved_release(hybrid_repository: tuple) -> None:
    root, cfg, _, _ = hybrid_repository
    with pytest.raises(ValueError, match="protected"):
        features.load_dataset(root, cfg, role="final_holdout")
    with pytest.raises(ValueError, match="reserved"):
        features.load_dataset(root, cfg, role="final_holdout", permit_confirmation=True)
    write_json(root / cfg["release"], {"SYNTHETIC": True})
    write_json(root / cfg["confirmation_state"], {"status": "completed", "opening_count": 1, "release_sha256": sha256_file(root / cfg["release"])})
    with pytest.raises(ValueError, match="reservation"):
        features.load_dataset(root, cfg, role="final_holdout", permit_confirmation=True)
