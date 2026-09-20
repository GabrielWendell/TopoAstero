# Split and holdout policy

The target population is split by star, never by light-curve segment, quarter, sector, simulation
realization tied to a star, or derived representation. The Stage 2 inventory resolves the 66
LEGACY star groups. Rudy remains a transparent descriptive benchmark and is excluded from the
three analysis partitions.

T2.8 completed the following before any topological output was computed:

1. resolved stable star identifiers and eligibility without topological outputs;
2. froze stratification variables and missingness handling;
3. generated development, internal-validation, and 20% final-holdout groups with the registered
   deterministic algorithm;
4. recorded the absence of an independent secret store in this portable source snapshot;
5. sealed the assignment file and its source with SHA-256; and
6. passed the no-star-overlap test.

The 65 non-Rudy stars were ranked into three equal-count `nu_max` strata from the checked Stage 1
reference table. Within each stratum, SHA-256 of the registered seed, stratum, and stable star ID
defines the order. Largest-remainder quotas produce 39 development, 13 internal-validation, and 13
final-holdout stars. Effective-temperature tertiles are recorded as a balance diagnostic, not used
to tune the assignment. All mission observations and later derived representations inherit their
star's role.

Because this distributable repository has no independent secrets facility and the labels were
already public literature data, it does not claim identity confidentiality. “Opening the holdout”
means using or inspecting topological results for those stars during analysis. That event still
requires authorization and an append-only log entry. Cleartext identities make the split auditable;
the immutable seal and process controls protect it from silent reassignment.

The policy record is `registries/split_policy.yaml`; the one-time log is
`registries/holdout_access_log.csv`. At Gate G2 that log still contains only its header. The frozen
assignment, content seal, and balance report are `registries/population_partitions.csv`,
`registries/split_attestation.json`, and `reports/stage2/partition_balance.json`.
