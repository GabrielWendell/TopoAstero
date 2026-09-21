from __future__ import annotations

from pathlib import Path

import pytest

from topoastero.cli import main

ROOT = Path(__file__).parents[2]


@pytest.mark.integration
def test_stage4_cli_passes(capsys: pytest.CaptureFixture[str]) -> None:
    main(["validate-stage4", "--root", str(ROOT), "--without-prior-stages"])
    assert (
        "Stage 4 analytic cases and stochastic simulation contract: PASS" in capsys.readouterr().out
    )


@pytest.mark.integration
def test_stage4_cli_reports_missing_contract(
    capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    with pytest.raises(SystemExit, match="1"):
        main(["validate-stage4", "--root", str(tmp_path), "--without-prior-stages"])
    assert "Stage 4 analytic/simulation contract failed" in capsys.readouterr().err
