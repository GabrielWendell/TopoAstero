# T0.7 - Risk register

The normative, testable register is `registries/risk_register.yaml`. Probability (P) and impact
(I) use L/M/H; `L-M` means the probability is currently between low and medium and must be resolved
at the next review.

| ID | Risk | P | I | Owner | Fallback |
| --- | --- | --- | --- | --- | --- |
| RISK-SCI-001 | PSD persistence duplicates prominence | M | H | Principal researcher | Publish equivalence/stability; remove novelty claim |
| RISK-SCI-002 | Topological echelle reduces to ridge score | M | H | Methods reviewer | Publish correct geometry and redundancy |
| RISK-SCI-003 | Delay topology has no phase information | H | M | Principal researcher | Retain negative result; drop from critical path |
| RISK-SCI-004 | Window artifacts mimic oscillations | M | H | Methods reviewer | Restrict domain; alias/reliability return |
| RISK-SCI-005 | Preprocessing dominates topology | M | H | Principal researcher | Diagnostic use; widen uncertainty; narrow claim |
| RISK-SCI-006 | Rudy baseline mismatch | L-M | H | Principal researcher | Pause TDA and reconcile conventions |
| RISK-SCI-007 | Half/double spacing aliases dominate | M | M | Principal researcher | Candidate set/posterior and flag |
| RISK-STAT-001 | LEGACY too small for flexible ML | H | H | Methods reviewer | Compact models and paired validation |
| RISK-SCI-008 | TESS Rudy detection inadequate | H | M | Principal researcher | Publish detectability boundary |
| RISK-MATH-001 | Bound too loose | M | M | Methods reviewer | Local/probabilistic bounds or exact cases |
| RISK-COMP-001 | MESA/GYRE delays core | M | H | Supervisor | Defer; published/asymptotic frequencies |
| RISK-COMP-002 | Compute/storage pressure | L-M | M | Principal researcher | Adaptive/chunked 1D-first program |
| RISK-PROG-001 | Defense deadline pressure | H | H | Supervisor | Freeze extensions and population breadth |
| RISK-DATA-001 | Archive identity/version drift | M | H | Data steward | Pin verified products; optional transfer |
| RISK-DATA-002 | Same-star leakage | L | H | Data steward | Invalidate, rebuild, and rerun |
| RISK-PROG-002 | Governance overhead | M | M | Principal researcher | Consolidate prose; retain controls |

Each machine record also contains early warning, mitigation, review date, and accountable role.
Trigger reviews happen immediately; otherwise the register is reviewed monthly and at every gate.

