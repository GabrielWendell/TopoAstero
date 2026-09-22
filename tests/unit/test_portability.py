from __future__ import annotations

from pathlib import Path

from topoastero.portability import (
    normalize_text_file_lf,
    repository_portability_issues,
    repository_relative_posix,
    serialized_posix_path,
    write_csv_lf,
    write_json_lf,
    write_text_lf,
)


def test_portable_repository_paths_use_forward_slashes(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    target = root / "results" / "stage3" / "table.csv"
    target.parent.mkdir(parents=True)
    target.touch()
    assert repository_relative_posix(target, root) == "results/stage3/table.csv"
    assert serialized_posix_path(r"results\stage3\table.csv") == "results/stage3/table.csv"


def test_canonical_writers_emit_lf_only(tmp_path: Path) -> None:
    csv_path = tmp_path / "table.csv"
    json_path = tmp_path / "payload.json"
    text_path = tmp_path / "note.txt"

    write_csv_lf(csv_path, [{"a": "1", "b": "2"}], fieldnames=["a", "b"])
    write_json_lf(json_path, {"b": 2, "a": 1})
    write_text_lf(text_path, "one\ntwo\n")

    for path in (csv_path, json_path, text_path):
        payload = path.read_bytes()
        assert b"\r" not in payload
        assert payload.endswith(b"\n")


def test_normalization_repairs_crlf_and_is_idempotent(tmp_path: Path) -> None:
    path = tmp_path / "artifact.csv"
    path.write_bytes(b"a,b\r\n1,2\r\n")
    assert normalize_text_file_lf(path) is True
    assert path.read_bytes() == b"a,b\n1,2\n"
    assert normalize_text_file_lf(path) is False


def test_portability_check_reports_newline_and_manifest_path_defects(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    (root / "results/stage3").mkdir(parents=True)
    (root / "results/stage4").mkdir(parents=True)
    (root / "results/stage5").mkdir(parents=True)
    (root / "artifact.csv").write_bytes(b"a,b\r\n1,2\r\n")
    write_json_lf(
        root / "results/stage3/run_manifest.json",
        {"config_path": r"configs\stage3_classical.yaml", "outputs": []},
    )
    write_json_lf(
        root / "results/stage4/run_manifest.json",
        {
            "config_path": "configs/stage4_simulation.yaml",
            "inputs": [{"path": r"data\derived\stage4\window.csv"}],
            "outputs": [{"path": r"results\stage4\table.csv"}],
        },
    )
    write_json_lf(
        root / "results/stage5/run_manifest.json",
        {
            "config_path": r"configs\stage5_tda.yaml",
            "inputs": [{"path": r"results\stage4\factorial_pilot.csv"}],
            "outputs": [{"path": r"results\stage5\features.csv"}],
        },
    )

    issues = repository_portability_issues(root)
    assert any("non-LF tracked text: artifact.csv" in issue for issue in issues)
    assert any("config_path" in issue for issue in issues)
    assert any("stage4/run_manifest.json:inputs" in issue for issue in issues)
    assert any("stage4/run_manifest.json:outputs" in issue for issue in issues)
    assert any("stage5/run_manifest.json:inputs" in issue for issue in issues)
    assert any("stage5/run_manifest.json:outputs" in issue for issue in issues)
