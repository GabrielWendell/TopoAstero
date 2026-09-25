# Locked Stage 4 confirmation protocol

The normative machine-readable record is `registries/stage4_confirmation_protocol.yaml`, version
1.0, status `locked`, frozen 2026-09-21.

The primary endpoint is the family-specific max-calibrated folded topological score at FWER 0.05,
with multiplicity spanning every registered trial spacing, filtration/smoothing choice, and
summary. Secondary endpoints are classical spacing error, calibrated detection probability, interval
coverage, and compute cost. Practical-equivalence margins and no-significance-stopping rules are
fixed in the registry.

Population partitions remain governed by `registries/split_policy.yaml`. Thresholds cannot be
refit after holdout access. Any uncalibrated construction is diagnostic-only or removed from the
confirmation analysis.
