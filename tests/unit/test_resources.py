from __future__ import annotations

import json
from pathlib import Path

from topoastero.resources import audit_resources, write_resource_audit


def test_offline_resource_audit(tmp_path: Path) -> None:
    record = audit_resources(tmp_path, check_network=False)
    assert record["archive_access"]["status"] == "offline_mode"
    assert record["persistence_benchmark"]["pairs_last_run"] > 1
    assert record["planning_targets"]["gpu_required_for_core"] is False
    output = tmp_path / "audit.json"
    written = write_resource_audit(tmp_path, output, check_network=False)
    assert json.loads(output.read_text(encoding="utf-8"))["audit_version"] == 1
    assert written["host"]["storage"]["free_bytes"] > 0

