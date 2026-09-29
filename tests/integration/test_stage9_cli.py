"""The CLI states both implementation integrity and pending science review."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parents[2]


def test_stage9_cli_reports_pending_review_without_claiming_gate_pass() -> None:
    completed = subprocess.run(
        [sys.executable, "-m", "topoastero", "validate-stage9", "--root", str(ROOT)],
        check=True, capture_output=True, text=True,
    )
    assert "implementation: PASS" in completed.stdout
    assert "scientific G9: review_pending" in completed.stdout
