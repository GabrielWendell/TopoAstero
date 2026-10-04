from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).parents[2]


@pytest.mark.integration
def test_stage10_cli_offline_snapshot_and_review_hold() -> None:
    run = subprocess.run([sys.executable, "-m", "topoastero", "validate-stage10", "--root", str(ROOT), "--without-prior-stages"], capture_output=True, text=True, check=False)
    assert run.returncode == 0, run.stdout + run.stderr
    assert "PASS" in run.stdout and "review_pending" in run.stdout


@pytest.mark.integration
def test_stage10_offline_reduced_headlines_replay() -> None:
    run = subprocess.run([sys.executable, str(ROOT / "workflows/replay_stage10_reduced.py")], capture_output=True, text=True, check=False)
    assert run.returncode == 0, run.stdout + run.stderr
    assert "not a raw-product" in run.stdout
