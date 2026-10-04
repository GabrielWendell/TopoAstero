from __future__ import annotations

from pathlib import Path

import pytest

from topoastero.provenance import sha256_file
from topoastero.stage10_validation import file_seal_issues, independent_review_accepted


def pending() -> dict[str, object]:
    return {"review_id": "TA-S10-INDEPENDENT-REVIEW-001", "status": "pending_external_review", "reviewed_snapshot": "reports/stage10/freeze_manifest.json", "reviewer_name": None, "reviewer_affiliation": None, "reviewer_independent_of_authors": None, "review_date": None, "document_sha256": None, "decision": None, "reproduced_claim_ids": []}


def test_file_seals_reject_escape_missing_and_stale(tmp_path: Path) -> None:
    path = tmp_path / "evidence.json"
    path.write_text("{}")
    seal = {"path": "evidence.json", "size_bytes": 2, "sha256": sha256_file(path)}
    assert file_seal_issues(tmp_path, [seal], "test") == []
    for name in ("../evidence.json", "/tmp/anywhere", "C:\\absolute", "sub\\file", ""):
        assert "unsafe path" in file_seal_issues(tmp_path, [{**seal, "path": name}], "test")[0]
    assert file_seal_issues(tmp_path, None, "test")
    assert file_seal_issues(tmp_path, [1], "test")
    path.write_text("changed")
    assert "stale seal" in file_seal_issues(tmp_path, [seal], "test")[0]


def test_pending_and_invalid_review_cannot_imply_approval(tmp_path: Path) -> None:
    review = pending()
    assert independent_review_accepted(tmp_path, review) == (False, [])
    for change in ({"reviewer_name": "automated"}, {"review_id": "wrong"}, {"status": "machine_pass"}, {"status": "accepted", "review_date": "not a date"}):
        accepted, issues = independent_review_accepted(tmp_path, {**review, **change})
        assert not accepted and issues


def test_exact_document_independent_review_validation(tmp_path: Path) -> None:
    snapshot = tmp_path / "reports/stage10/freeze_manifest.json"
    snapshot.parent.mkdir(parents=True)
    snapshot.write_text("{}")
    # Synthetic unit-test attestation only; the actual repository record stays empty.
    review = {**pending(), "status": "accepted", "reviewer_name": "Unit-test fixture", "reviewer_affiliation": "Synthetic fixture", "reviewer_independent_of_authors": True, "review_date": "2026-09-30", "document_sha256": sha256_file(snapshot), "decision": "accepted", "reproduced_claim_ids": [f"P1-C{i:02d}" for i in range(1, 9)]}
    assert independent_review_accepted(tmp_path, review) == (True, [])
    for change in ({"reviewer_independent_of_authors": False}, {"reproduced_claim_ids": []}, {"review_date": "2099-01-01"}):
        assert independent_review_accepted(tmp_path, {**review, **change})[0] is False
    snapshot.write_text("new document")
    assert independent_review_accepted(tmp_path, review)[0] is False


@pytest.mark.parametrize("value", [None, "", 123])
def test_invalid_seal_path_type(tmp_path: Path, value: object) -> None:
    assert file_seal_issues(tmp_path, [{"path": value}], "test")
