from __future__ import annotations

from pathlib import Path

import pytest

from topoastero.cli import main

ROOT = Path(__file__).parents[2]


@pytest.mark.integration
def test_stage5_cli_passes(capsys: pytest.CaptureFixture[str]) -> None:
    main(["validate-stage5", "--root", str(ROOT), "--without-prior-stages"])
    assert "Stage 5 TDA core and representation-audit contract: PASS" in capsys.readouterr().out


@pytest.mark.integration
def test_stage5_cli_reports_missing_contract(
    capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    with pytest.raises(SystemExit, match="1"):
        main(["validate-stage5", "--root", str(tmp_path), "--without-prior-stages"])
    assert "Stage 5 TDA/representation-audit contract failed" in capsys.readouterr().err

