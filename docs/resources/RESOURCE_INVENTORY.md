# T0.8 - Resource inventory and feasibility note

**Inventory version:** 1.0  
**Initial audit:** 2026-09-18  
**Regenerate:** `uv run topoastero audit-resources --root . --output reports/stage0/resource_audit.json --check-network`

## Verified Stage 0 execution environment

The implementation environment exposed 9 logical CPUs, approximately 21 GiB RAM, and approximately
28 GiB free workspace storage. It is sufficient for tests, deterministic one-dimensional
persistence, compact simulations, and development. It is not the promised allocation for the full
publication program. The generated machine record, including exact platform and benchmark timing,
is `reports/stage0/resource_audit.json`.

The Stage 0 benchmark computes exact H0 superlevel persistence for a 512-sample signal 100 times.
This establishes that the package, configuration, output, and provenance path works; it is not a
performance estimate for cubical echelle grids or nested population resampling.

## Full-program planning envelope

| Resource | Planning value | Stage 0 decision |
| --- | --- | --- |
| CPU | 50,000-100,000 CPU-hours for full simulation/validation program | Request/identify batch allocation before scaling S4 |
| Temporary storage | 2-5 TB | Current workspace is development-only; institutional storage required |
| Archival derived products | Under 200 GB target | Archive compact tables/manifests first; profile expensive products |
| GPU | Not required for core thesis | Do not make GPU access a critical dependency |
| Workstation | Baselines and 1D persistence | Approved for development and bounded pilots |

Actual requests replace planning values after the S4 factorial pilot. Scaling is prohibited when
pilot time/storage extrapolation exceeds the available allocation by a factor of two.

## Software and licenses

| Component | Stage | License/status | Decision |
| --- | --- | --- | --- |
| TopoAstero | Core | BSD-3-Clause | Installed from locked environment |
| Python | Core | PSF | Python 3.12 reference; 3.11-3.13 CI |
| PyYAML | Core | MIT | Locked in `uv.lock` |
| MESA | Optional S13 | LGPL-3.0; official release required | Not detected in Stage 0 runtime; capability deferred without blocking core |
| GYRE | Optional S13 | GPL-3.0 | Not detected in Stage 0 runtime; may use published frequencies/asymptotic simulations |
| MAST | Core data source | Public archive; product-specific terms/citations | HTTPS endpoint and query tooling must be tested again in S2 acquisition environment |

MESA/GYRE absence is an explicit bounded limitation, not a Stage 0 failure. If installation,
convergence, or grid design consumes more than one review cycle, cap the grid and use published mode
frequencies or asymptotic simulations.

## Archive access

The MAST portal is publicly reachable through HTTPS as of the Stage 0 review, but the executable
resource audit probes access from the actual runtime because institutional networks and credentials
can differ. A failed probe blocks acquisition, not governance: T2 records the network error,
preserves exact queries, and retries from an approved environment. No proprietary data are required.

## Compute fallback ladder

1. Exact/analytic and one-dimensional persistence.
2. Reduced simulation design with adaptive allocation and cached sufficient products.
3. Chunked cubical calculations and fewer non-primary summaries.
4. Compact star validation with paired low-dimensional statistics.
5. Defer large MESA/GYRE, broad TESS, and high-dimensional models.

The fallback never removes null calibration, classical controls, uncertainty, or provenance.

