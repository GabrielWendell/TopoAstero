from __future__ import annotations

from pathlib import Path

import pytest

from topoastero.cli import main

ROOT = Path(__file__).parents[2]


@pytest.mark.integration
def test_cli_hash_checksum_and_validation(capsys: pytest.CaptureFixture[str], tmp_path: Path) -> None:
    main(["hash-config", str(ROOT / "configs/smoke.yaml")])
    assert len(capsys.readouterr().out.strip()) == 64

    payload = tmp_path / "payload"
    payload.write_text("x", encoding="utf-8")
    main(["checksum", str(payload)])
    assert len(capsys.readouterr().out.strip()) == 64

    main(["validate-stage0", "--root", str(ROOT), "--without-smoke"])
    assert "PASS" in capsys.readouterr().out

    main(["check-portability", "--root", str(ROOT)])
    assert "PASS" in capsys.readouterr().out


@pytest.mark.integration
def test_cli_resource_audit(capsys: pytest.CaptureFixture[str], tmp_path: Path) -> None:
    output = tmp_path / "resources.json"
    main(["audit-resources", "--root", str(tmp_path), "--output", str(output)])
    assert output.is_file()
    assert '"audit_version": 1' in capsys.readouterr().out

