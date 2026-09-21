# Derived tier

Derived products are generated from raw parent checksums plus an immutable configuration and code
version. Use content-addressed paths and never edit an output in place. Compact publishable tables
may be promoted to the archive/release tier.

`stage4/mission_window_templates.csv` is a compact derived exception retained for reproducibility.
It contains observing intervals and source payload hashes only, never mission fluxes. Rebuild it
from the verified external FITS cache with `workflows/build_stage4_window_templates.py`.
