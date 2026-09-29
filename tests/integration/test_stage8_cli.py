"""User-facing Stage 8 validator and rerunnable notebook integration."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from topoastero.cli import main

ROOT = Path(__file__).parents[2]


@pytest.mark.integration
def test_stage8_cli_passes(capsys: pytest.CaptureFixture[str]) -> None:
    main(["validate-stage8", "--root", str(ROOT), "--without-prior-stages"])
    assert "Stage 8 cylindrical-echelle geometry and bounded-inference contract: PASS" in capsys.readouterr().out


@pytest.mark.integration
def test_stage8_cli_missing_contract(capsys: pytest.CaptureFixture[str], tmp_path: Path) -> None:
    with pytest.raises(SystemExit, match="1"):
        main(["validate-stage8", "--root", str(tmp_path), "--without-prior-stages"])
    assert "Stage 8 cylindrical-echelle contract failed" in capsys.readouterr().err


@pytest.mark.integration
def test_stage8_notebook_code_executes_top_to_bottom(capsys: pytest.CaptureFixture[str]) -> None:
    notebook = json.loads((ROOT / "notebooks/08_cylindrical_echelle.ipynb").read_text())
    namespace: dict[str, object] = {"__name__": "__notebook__"}
    previous = Path.cwd()
    try:
        os.chdir(ROOT)
        for cell in notebook["cells"]:
            if cell["cell_type"] == "code":
                exec("".join(cell["source"]), namespace)
    finally:
        os.chdir(previous)
    assert "geometry_only" in capsys.readouterr().out
