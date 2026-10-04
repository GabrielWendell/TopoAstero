from pathlib import Path

import pytest

from topoastero.hybrid.cli import main


@pytest.mark.integration
def test_stage12_cli_validates_without_opening_holdout(capsys) -> None:
    root = Path(__file__).parents[2]
    assert main(["--root", str(root), "validate"]) == 0
    assert "implementation: PASS" in capsys.readouterr().out
    assert not (root / "registries/stage12_confirmation.json").exists()
