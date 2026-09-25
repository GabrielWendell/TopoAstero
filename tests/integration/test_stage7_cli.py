from __future__ import annotations

import json
from pathlib import Path

import matplotlib
import pytest

from topoastero.cli import main

matplotlib.use("Agg")

ROOT = Path(__file__).parents[2]


@pytest.mark.integration
def test_stage7_cli_passes(capsys: pytest.CaptureFixture[str]) -> None:
    main(["validate-stage7", "--root", str(ROOT), "--without-prior-stages"])
    assert "Stage 7 delay-topology and phase-information contract: PASS" in capsys.readouterr().out


@pytest.mark.integration
def test_stage7_cli_reports_missing_contract(
    capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    with pytest.raises(SystemExit, match="1"):
        main(["validate-stage7", "--root", str(tmp_path), "--without-prior-stages"])
    assert "Stage 7 delay-topology contract failed" in capsys.readouterr().err


@pytest.mark.integration
def test_stage7_notebook_code_executes_top_to_bottom(capsys: pytest.CaptureFixture[str]) -> None:
    notebook = json.loads((ROOT / "notebooks/07_delay_embedding_phase_test.ipynb").read_text())
    namespace: dict[str, object] = {"__name__": "__notebook__"}
    previous = Path.cwd()
    try:
        import os

        os.chdir(ROOT)
        for cell in notebook["cells"]:
            if cell["cell_type"] == "code":
                exec("".join(cell["source"]), namespace)
    finally:
        os.chdir(previous)
    output = capsys.readouterr().out
    assert "drop calibrated_negative_result 48 3" in output
