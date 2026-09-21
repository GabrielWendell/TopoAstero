from __future__ import annotations

from pathlib import Path

import pytest

from topoastero.cli import main

ROOT = Path(__file__).parents[2]


@pytest.mark.integration
def test_stage3_cli_passes(capsys: pytest.CaptureFixture[str]) -> None:
    main(["validate-stage3", "--root", str(ROOT), "--without-prior-stages"])
    assert (
        "Stage 3 classical baseline and observation-model contract: PASS"
        in capsys.readouterr().out
    )


@pytest.mark.integration
def test_stage3_cli_reports_missing_contract(
    capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    with pytest.raises(SystemExit, match="1"):
        main(["validate-stage3", "--root", str(tmp_path), "--without-prior-stages"])
    assert "Stage 3 classical-baseline contract failed" in capsys.readouterr().err
