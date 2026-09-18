from __future__ import annotations

import json
from pathlib import Path

import pytest

from topoastero.smoke import run_smoke

ROOT = Path(__file__).parents[2]


@pytest.mark.integration
def test_smoke_workflow_is_deterministic(tmp_path: Path) -> None:
    first = run_smoke(ROOT / "configs/smoke.yaml", tmp_path / "first")
    second = run_smoke(ROOT / "configs/smoke.yaml", tmp_path / "second")
    assert first["summary"] == second["summary"]
    assert first["summary"]["essential_pair_count"] == 1
    assert first["summary"]["finite_pair_count"] > 5
    for filename in (
        "signal.csv",
        "persistence_pairs.csv",
        "summary.json",
        "smoke_figure.svg",
        "run_manifest.json",
    ):
        assert (tmp_path / "first" / filename).is_file()
    manifest = json.loads((tmp_path / "first/run_manifest.json").read_text(encoding="utf-8"))
    assert manifest["benchmark"]["seconds_per_run"] > 0.0
    assert set(manifest["outputs"]) == {
        "signal.csv",
        "persistence_pairs.csv",
        "summary.json",
        "smoke_figure.svg",
    }
    assert "<svg" in (tmp_path / "first/smoke_figure.svg").read_text(encoding="utf-8")


@pytest.mark.integration
def test_smoke_rejects_nonpositive_benchmark_repeats(tmp_path: Path) -> None:
    config = tmp_path / "bad.yaml"
    config.write_text(
        """workflow_id: bad
experiment_id: TA-S00-T08-BAD-R001
hypothesis_id: DIAGNOSTIC
split_role: analytic
random_seed: 1
signal:
  samples: 8
  fundamental_cycles: 1
  secondary_cycles: 2
  secondary_amplitude: 0.1
  noise_sigma: 0
persistence:
  include_zero: false
benchmark:
  repeats: 0
""",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="positive"):
        run_smoke(config, tmp_path / "out")
