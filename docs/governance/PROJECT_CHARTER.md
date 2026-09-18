# D0.1 - TopoAstero project charter

**Charter version:** 1.0  
**Frozen:** 2026-09-18  
**Applies from:** S0  
**Owner:** Principal researcher  
**Scientific approver:** Supervisor/PI role

## Purpose

TopoAstero develops, mathematically characterizes, and empirically validates physically
interpretable topological observables of solar-like oscillations. Persistent topology must either
improve or certify asteroseismic inference under realistic limitations, or produce a rigorous,
publishable boundary showing when it is redundant or unreliable.

## Controlled claims

1. **Claim I - identifiable object.** A retained topological construction has a mathematically
   identifiable relationship to controlled oscillatory or spectral structure.
2. **Claim II - calibrated estimator.** Its estimator and null distribution are calibrated under
   stochastic excitation, noise, sampling, backgrounds, and mission windows.
3. **Claim III - stellar recovery.** It recovers or certifies information in Rudy and generalizes
   to an independently selected Kepler population.
4. **Claim IV - incremental value or rigorous redundancy.** It adds information beyond strong
   classical controls, or defines its redundancy and failure domain, including mission transfer.

Claims are nested. Evidence for a later claim cannot repair a failure of an earlier one.

## Scope

### Core

- Analytic sinusoids, Lorentzian peaks, mode combs, and idealized ridges.
- Stochastic solar-like simulations with realistic backgrounds, windows, cadence, damping, and
  signal-to-noise variation.
- Five candidate representations: scalar light curve, delay cloud, normalized PSD, mode cloud,
  and periodic echelle image/ridge graph.
- KIC 10963065 (Rudy) as a transparent benchmark.
- Compact, star-grouped Kepler LEGACY confirmation with classical baselines and nulls.
- Interpretable estimators, uncertainty, physical localization, negative controls, and reproducible
  release artifacts.

### Bounded extension

- Kepler-to-TESS degradation and actual Rudy TESS sectors after a detectability gate.
- Compact MESA/GYRE cases after profiling and after the core is stable.
- A small hybrid classical-topological model only after features are locked.

### Excluded from the thesis-critical path

- Uniform analysis of all Kepler targets; broad red-giant or mixed-mode surveys.
- High-dimensional or topological deep learning without sample-size and ablation justification.
- Large MESA/GYRE grids, multiparameter persistence, and broad TESS population work.
- Replacing full Bayesian peak bagging or inferring evolution without conventional models.

## Priorities and stop rules

Correctness, leakage control, null calibration, provenance, uncertainty, and a strong classical
baseline outrank method breadth. If schedule or compute pressure grows, extension tasks are removed
first, population breadth second, and the central claim last. Nulls, provenance, uncertainty, and
baseline comparisons are never removed to save time.

A representation is dropped from the critical path when a registered topology-free ablation
matches it, its null is uncalibrated, its output is dominated by preprocessing, or its physical
localization cannot be recovered. The negative result is retained.

## Roles and responsibility matrix

| Role | Accountabilities | Decision authority |
| --- | --- | --- |
| Principal researcher (Gabriel Wendell) | Implementation, manifests, analysis ledger, tests, reports, first scientific recommendation | Routine implementation and preregistered analyses |
| Supervisor/PI | Scientific scope, gate approval, holdout opening, authorship resolution | Final authority on scope and scientific gate disputes |
| Data steward (initially principal researcher) | Product identity, checksums, licenses, retention, backup verification | Rejects data without adequate provenance |
| Methods reviewer (assigned per milestone) | Statistical/TDA review, leakage audit, null and uncertainty review | Required approval for headline-method changes |
| Reproduction reviewer (independent of the producing run) | Clean-environment rerun and artifact audit | Can block release or gate passage for irreproducibility |

Unassigned people are roles, not assumed collaborators. Names are added through change control
before the role authorizes a gate.

## Working rhythm

- **Weekly:** issue board, experiment ledger, hashes, risks, test suite, one immutable result, and
  one decision for the next meeting.
- **Biweekly:** supervisor meeting centered on a named decision and its evidence.
- **Monthly:** stage/gate, compute, writing, risks, and claim review.
- **Quarterly:** red-team review of leakage, nulls, negative results, and scope.
- **Before holdout:** the complete checklist in the protocol is signed.
- **Before release/submission:** independent clean-environment reproduction and citation/data audit.

Authorship is discussed at project launch, at each manuscript charter, when contributions change
materially, and before submission. Contributions are recorded using CRediT roles; author order is
not inferred from software commits alone.

## Change control

Every scientific change records its motivation, affected hypothesis/stage/deliverable, whether
relevant data were inspected, expected benefit, leakage risk, schedule cost, alternatives,
decision, approver, and version in `registries/change_log.csv`.

- Before holdout access, the supervisor/PI approves changes that can affect a headline conclusion.
- After holdout access, correctness fixes are mandatory, trigger a complete affected rerun, and are
  labeled post-confirmation. A changed analysis cannot regain confirmatory status without a new
  independent dataset.
- Editorial changes that cannot alter computation require review but not a scientific change
  request.

## Definition of done and Gate G0

A stage is complete only when its deliverables exist, acceptance tests pass or a signed exception
exists, versions/configurations/seeds are recorded, figures regenerate from tables, failures and
limitations are documented, and the next stage has no hidden manual dependency.

**G0 passes** when a collaborator can install the locked environment, run the smoke workflow, find
every planned dataset and H1-H6 without oral instructions, and see that every conclusion-changing
open choice is either frozen or assigned to a named pilot decision. `reports/stage0/` holds the
acceptance evidence.

