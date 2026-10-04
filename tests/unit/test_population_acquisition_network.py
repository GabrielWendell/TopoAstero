"""Network-resilience tests for Stage 11 mission acquisition."""

from __future__ import annotations

from pathlib import Path

import pytest

import topoastero.population_acquisition as acquisition


class _Response:
    def __init__(self, payload: bytes) -> None:
        self.payload = payload
        self.offset = 0

    def __enter__(self) -> _Response:
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def read(self, size: int) -> bytes:
        if self.offset >= len(self.payload):
            return b""
        block = self.payload[self.offset : self.offset + size]
        self.offset += len(block)
        return block


def test_download_payload_retries_timeout_then_succeeds(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    payload = b"stage11-network-fixture"
    calls: list[int] = []

    def fake_urlopen(*args: object, **kwargs: object) -> _Response:
        calls.append(1)
        if len(calls) < 3:
            raise TimeoutError("synthetic read timeout")
        return _Response(payload)

    monkeypatch.setattr(acquisition.urllib.request, "urlopen", fake_urlopen)
    monkeypatch.setattr(acquisition.time, "sleep", lambda _: None)
    destination = tmp_path / "payload.fits"
    acquisition._download_payload(
        "https://example.invalid/payload",
        destination,
        expected_size=len(payload),
        timeout=240.0,
        retries=4,
        retry_backoff=2.0,
    )
    assert destination.read_bytes() == payload
    assert len(calls) == 3
    assert not destination.with_suffix(".fits.part").exists()


def test_download_payload_exhaustion_is_atomic(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_urlopen(*args: object, **kwargs: object) -> _Response:
        raise TimeoutError("synthetic read timeout")

    monkeypatch.setattr(acquisition.urllib.request, "urlopen", fake_urlopen)
    monkeypatch.setattr(acquisition.time, "sleep", lambda _: None)
    destination = tmp_path / "payload.fits"
    with pytest.raises(OSError, match="failed after 3 attempts"):
        acquisition._download_payload(
            "https://example.invalid/payload",
            destination,
            expected_size=10,
            timeout=240.0,
            retries=3,
            retry_backoff=2.0,
        )
    assert not destination.exists()
    assert not destination.with_suffix(".fits.part").exists()


def test_download_payload_rejects_invalid_policy(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="timeout/retries/backoff"):
        acquisition._download_payload(
            "https://example.invalid/payload",
            tmp_path / "payload.fits",
            expected_size=1,
            timeout=0.0,
            retries=1,
            retry_backoff=0.0,
        )
