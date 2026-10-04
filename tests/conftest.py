"""Stage 12 synthetic fixtures; these never touch the observational holdout."""
from __future__ import annotations

import math
import shutil
from pathlib import Path

import pytest

from topoastero.hybrid.features import CLASSICAL, TOPOLOGY, load_config
from topoastero.population_store import seal, write_json

ROOT = Path(__file__).parents[1]


@pytest.fixture
def hybrid_repository(tmp_path: Path) -> tuple[Path, dict, list[dict], list[dict]]:
    root = tmp_path / "synthetic_hybrid"
    for name in ("configs/stage12_hybrid.yaml", "configs/stage11_legacy.yaml", "registries/population_partitions.csv", "registries/split_attestation.json",
                 "registries/stage12_tasks.csv", "registries/stage12_features.csv", "docs/protocols/STAGE12_HYBRID_PROTOCOL.md",
                 "environment/stage12.Dockerfile", "pyproject.toml", "uv.lock", "data/reference/stellar_references.csv", "paper2/references.bib"):
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / name, path)
    (root / "src/topoastero/hybrid").mkdir(parents=True)
    (root / "src/topoastero/hybrid/synthetic.py").write_text("# SYNTHETIC source fixture\n")
    (root / "workflows").mkdir()
    write_json(root / "reports/stage11/G11_ACCEPTANCE.json", {"scientific_population_gate_passed": False})
    cfg = load_config(root)
    rows = []
    for i in range(30):
        numax, dnu = 2000.0 + i * 10, 100.0 + i * .15
        correction = .15 if i % 2 else .015
        features = dict(zip(CLASSICAL + TOPOLOGY, [math.log(numax), math.log(dnu), math.log(2+i*.01), .9+i*.001,
                                                  math.log(30+i*.5), math.log(.3+i*.01), .01+i*.001,
                                                  .4+i*.001, .5+i*.002, -.1+i*.001, .6+i*.002], strict=True))
        rows.append({"stable_star_id": f"KIC {3000000+i}", "role": "development", "features": features,
                     "targets": {"numax": numax*math.exp(correction), "dnu": dnu*math.exp(correction)},
                     "classical": {"numax": numax, "dnu": dnu}, "flags": []})
    ledger = [{"stable_star_id": r["stable_star_id"], "role": r["role"], "included": True, "upstream_status": "SYNTHETIC"} for r in rows]
    write_json(root / "synthetic_inputs.json", {"rows": rows, "observational": False})
    return root, cfg, rows, ledger


@pytest.fixture
def hybrid_fitted(hybrid_repository: tuple, monkeypatch: pytest.MonkeyPatch) -> tuple:
    from topoastero.hybrid import pipeline
    root, cfg, rows, ledger = hybrid_repository
    monkeypatch.setattr(pipeline, "load_dataset", lambda r, c: (rows, ledger, [seal(root, root / "synthetic_inputs.json")]))
    pipeline.run_development(root, cfg)
    return hybrid_repository
