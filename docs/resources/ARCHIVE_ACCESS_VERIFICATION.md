# Archive-access verification record

**Checked:** 2026-09-18  
**Target:** `https://mast.stsci.edu/portal/Mashup/Clients/Mast/Portal.html`

Two checks were separated deliberately:

1. The public STScI MAST portal was reachable through an independent HTTPS web fetch during the
   Stage 0 review.
2. The executable audit from the current package runtime attempted the same endpoint and returned
   `URLError`; it did not establish programmatic access from this compute environment. The exact
   result is preserved in `reports/stage0/resource_audit.json`.

This is a **registered environment limitation**, not evidence that MAST is unavailable. Before T2
acquisition, run the audit from the intended workstation/HPC login node, then execute a read-only
MAST metadata query and record response timestamp, query, tool version, and product IDs. Failure in
that environment blocks acquisition and triggers `RISK-DATA-001`; it does not authorize an
unrecorded mirror or mutable local-file workaround.

