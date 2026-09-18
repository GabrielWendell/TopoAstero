# Split and holdout policy

The target population is split by star, never by light-curve segment, quarter, sector, simulation
realization tied to a star, or derived representation. The exact inventory is not yet valid at S0,
so assigning named stars now would be false precision and could leak the future holdout.

T2.8 will:

1. resolve stable star identifiers and eligibility without topological outputs;
2. freeze stratification variables and missingness handling;
3. generate development, internal-validation, and approximately 20% final-holdout groups with the
   registered deterministic algorithm;
4. encrypt or otherwise access-control the holdout assignment where infrastructure permits;
5. publish the assignment hash immediately and the identities at registered opening; and
6. run the no-star-overlap test.

The policy record is `registries/split_policy.yaml`; the one-time log is
`registries/holdout_access_log.csv`. At Stage 0 that log must contain only its header.

