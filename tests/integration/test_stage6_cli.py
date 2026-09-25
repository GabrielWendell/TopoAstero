from __future__ import annotations

from pathlib import Path

import pytest

from topoastero.cli import main

ROOT = Path(__file__).parents[2]


@pytest.mark.integration
def test_stage6_cli_passes(capsys: pytest.CaptureFixture[str]) -> None:
    main(["validate-stage6", "--root", str(ROOT), "--without-prior-stages"])
    assert "Stage 6 persistent power-spectrum topology contract: PASS" in capsys.readouterr().out


@pytest.mark.integration
def test_stage6_cli_reports_missing_contract(
    capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    with pytest.raises(SystemExit, match="1"):
        main(["validate-stage6", "--root", str(tmp_path), "--without-prior-stages"])
    assert "Stage 6 PSD-topology contract failed" in capsys.readouterr().err

