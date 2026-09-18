"""Unattended entry point equivalent to the documented CLI smoke command."""

from __future__ import annotations

from topoastero.smoke import run_smoke

if __name__ == "__main__":
    run_smoke("configs/smoke.yaml", "results/smoke")

