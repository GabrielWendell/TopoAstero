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
