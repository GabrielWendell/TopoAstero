from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).parents[2]


@pytest.mark.integration
def test_stage11_cli_validates_without_opening_holdout() -> None:
    run = subprocess.run([sys.executable, "-m", "topoastero.population_cli", "--root", str(ROOT), "validate", "--without-prior-stages"],
                         capture_output=True, text=True, check=False)
    assert run.returncode == 0, run.stdout + run.stderr
    assert "PASS" in run.stdout and "population_pending" in run.stdout


@pytest.mark.integration
def test_stage11_replay_and_holdout_role_guard() -> None:
    run = subprocess.run([sys.executable, str(ROOT / "workflows/replay_stage11_reduced.py")], capture_output=True, text=True, check=False)
    assert run.returncode == 0, run.stdout + run.stderr
    assert "not a raw-product" in run.stdout
    guarded = subprocess.run([sys.executable, "-m", "topoastero.population_cli", "run-development", "--cache-dir", "data/raw", "--role", "final_holdout"],
                             cwd=ROOT, capture_output=True, text=True, check=False)
    assert guarded.returncode != 0 and "invalid choice" in guarded.stderr
