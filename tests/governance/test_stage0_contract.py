from __future__ import annotations

from pathlib import Path

import pytest

from topoastero.validation import validate_stage0

ROOT = Path(__file__).parents[2]


@pytest.mark.governance
def test_complete_stage0_contract() -> None:
    assert validate_stage0(ROOT, require_smoke=True) == []

