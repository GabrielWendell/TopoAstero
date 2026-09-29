# Configuration policy

Every scientific run starts from an immutable YAML configuration. The parsed mapping is serialized
as canonical sorted JSON and hashed with SHA-256. Formatting or comments do not change the hash;
any semantic value does.

Configurations used for a released result must never be edited in place. Copy the file, increment
its `schema_version` or experiment identifier, record the change request, and regenerate all
dependent outputs.

`stage3_classical.yaml` freezes the exact Rudy mission subset, both classical estimators,
background/window/echelle conventions, mode matching, branch registry, bootstrap seed/resamples,
TESS marginal-detection rule, and G3 tolerances. It must be changed under a new run ID.

`stage4_simulation.yaml` freezes analytic conventions, oscillator and observation models, the
72-cell pilot factors, seven null families, multiplicity scope, split calibration/evaluation
sizes, uncertainty coverage rules, compute budget, seeds, and G4 tolerances. It must be changed
under a new run ID and a new locked confirmation-protocol version.

`stage5_tda.yaml` freezes five representation filtrations, the common F2/essential-class policy,
bounded landmark and grid resolutions, independent null streams, nine nuisance audits, redundancy
and ablation methods, retain/drop criteria, seeds, and G5 tolerances. Any semantic change requires
a new run ID and selection-registry version before population topology is inspected.

`stage6_psd_topology.yaml` freezes the primary and sensitivity normalizations, exact path-H0 rules,
`nu_max` interval construction, half/nominal/double comb candidates, ACF/PSPS controls, matched
maximum-statistic nulls, robustness branches, five quality flags, and G6 limits. Any semantic change
requires a new run ID and a new pre-execution simulation lock.

`stage7_delay_topology.yaml` freezes the 24-cell simulation-only panel, delay and embedding rules,
unreduced VR persistence, PSD-preserving nulls, classical controls, rolling segmentation, and the
dual-path retain/drop decision. Any semantic change requires a new run ID and pre-execution lock.
