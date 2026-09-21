from __future__ import annotations

from pathlib import Path

import pytest

from topoastero.cli import main

ROOT = Path(__file__).parents[2]


@pytest.mark.integration
def test_stage1_cli_passes(capsys: pytest.CaptureFixture[str]) -> None:
    main(["validate-stage1", "--root", str(ROOT), "--without-stage0"])
    assert "Stage 1 literature and benchmark contract: PASS" in capsys.readouterr().out


@pytest.mark.integration
def test_stage1_cli_reports_missing_contract(
    capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    with pytest.raises(SystemExit, match="1"):
        main(["validate-stage1", "--root", str(tmp_path), "--without-stage0"])
    assert "Stage 1 evidence contract failed" in capsys.readouterr().err
