# Stage 9: definitions, proofs, and claim boundaries

**Run:** `TA-S09-MATH-R001` · **State:** proof draft for independent review · **Data:**
analytic constructions and seeded simulations only. The Stage 8 decision remains
`geometry_only`; none of the following establishes incremental estimator utility.
Claim IDs below are used in the numerical audit and review checklist.

## 1. Mathematical objects and conventions (T9.1)

- A *path* has vertices \(0,\ldots,m-1\), edges between neighbors, and a finite
  real field \(f\). At threshold \(t\), vertices of height at least \(t\) and
  edges whose two endpoints are present enter the superlevel filtration.
  Homology uses \(\mathbb F_2\). Generic peak statements assume all vertex
  heights distinct. Endpoints have one neighbor; the global maximum gives an
  essential \(H_0\) class with no death or finite prominence. Ties are
  resolved in the implementation by peak index, but are excluded from the
  generic identity. A masked or disconnected path has one essential class
  per component, so needs componentwise conventions.
- The Stage 8 field is sampled at 24 angular centers on a finite
  \(I\times S^1\). It has a periodic angular seam and no radial wrap. Missing
  vertices and incident cells are omitted, not filled. A cubical cell enters
  at its **minimum vertex value**; coefficients are \(\mathbb F_2\). Stability
  comparisons keep this exact mask, cell incidence, frequency interpolation
  locations, and filtration rule fixed. Essential classes are matched only
  to essential classes; the package's finite bottleneck API excludes them.
- A ridge phase is \(u(\nu;\Delta)=\{\nu/\Delta\}\in\mathbb R/\mathbb Z\), with
  circular geodesic distance \(d_\circ(a,b)=\min_{k\in\mathbb Z}|a-b-k|\).
  The graph retains up to five local maxima per trial row, connects candidates
  in **adjacent** rows at distance at most \(J=0.17\) cycles, and scores a
  path of length \(L\) among \(N\) valid rows as
  \((L/N)\exp(-\bar d/J)(0.5+0.5s)\), where \(0\le s\le1\).
- An ideal two-coordinate delay observation is
  \(X(t)=(A\sin(\omega t+\phi),A\sin(\omega(t+\tau)+\phi))\), with
  \(A>0,\omega=2\pi\nu\), Euclidean coordinates and continuous phase coverage.
  A finite sampled cloud is a subset of the ellipse, not the full ellipse.
- In the stochastic statement each **unsmoothed** positive raw bin ratio
  \(X_i=P_i/S_i\) has marginal \(\mathrm{Gamma}(k,1/k)\), with known \(S_i>0\)
  and shape \(k>0\). Independence is not required for the union bound.
  Estimated backgrounds, interpolation, smoothing, selection, and red noise
  require their own verified nuisance bound/model. No Gaussian flux error is
  silently promoted to a Gamma PSD law.

## 2. Exact idealized relations (T9.2)

**S9-P1 (proposition; known peak identity).** Let \(p\) be a strict local
maximum of a generic, connected path. Let \(H_p\) be the set of peaks with
higher value. If \(H_p\ne\varnothing\), define
\[
 s_p=\max_{h\in H_p}\ \min_{\min(p,h)\le i\le\max(p,h)} f_i.
\]
The finite elder-rule \(H_0\) lifetime born at \(p\) is \(f_p-s_p\).
The unique global maximum is essential. **Proof.** Its component first meets
the component of a higher peak at the largest bottleneck level along any path
to a higher peak; on a path graph the route between two vertices is unique.
The elder rule kills the lower-birth component at that merge. Endpoint peaks
use the same unique route. The independent \(O(m^2)\) minimax computation is
compared with Stage 5's union-find in `test_mathematical_relations.py` and the
Stage 9 seeded audit. This is an equivalence, never a novel signal strength.

**S9-P2 (proposition; ideal sinusoid).** The continuous delay locus has
semiaxes
\[
 A\sqrt{1+|\cos(2\pi\nu\tau)|},\quad
 A\sqrt{1-|\cos(2\pi\nu\tau)|}.
\]
**Proof.** With \(z=(\sin\varphi,\cos\varphi)^T\) on the unit circle,
\(X=A\left(\begin{smallmatrix}1&0\\\cos\delta&\sin\delta\end{smallmatrix}\right)z\).
The Gram matrix has eigenvalues \(A^2(1\pm|\cos\delta|)\).
At \(\delta\in\pi\mathbb Z\), the minor axis is zero. A sparse sample need
not attain either axis. If each sampled scalar coordinate has absolute error
at most \(e\), each delay point moves by at most \(\sqrt2e\), pairwise
distances by at most \(2\sqrt2e\); this controls the fixed-vertex Euclidean
Vietoris–Rips filtration, **not** the coverage of the continuous ellipse.
Phase gaps and changing landmark selection are separate effects.

**S9-P3 (proposition; correctly identified small separation).** For identified
\(\nu_{n,0}\), \(\nu_{n-1,2}\), \(\nu_{n,1}\), \(\nu_{n-1,1}\), write
\(a=\nu_{n,0}-\nu_{n-1,2}\), \(b=\nu_{n,1}-\nu_{n-1,1}>0\), and choose a
*lifted* angular difference \(\Delta\theta_{02}=2\pi a/\Delta\), with a
trial \(\Delta>0\). Then
\[
 r_{02}=a/b,\quad \Delta\theta_{02}/(2\pi)=a/\Delta,\quad
 |r_{02}-\Delta\theta_{02}/(2\pi)|=|a|\,|b^{-1}-\Delta^{-1}|.
\]
It is approximate only if \(b\simeq\Delta\). To recover a lifted difference
from modulo angles, both identity and integer wrap/order assignment must be
known (e.g. \(0<a<\Delta\)); an unlabeled ridge cannot provide this.
Five-point \(r_{01}\) and \(r_{10}\) are not angular identities.

## 3. Fixed-domain perturbation and a new conditional graph bound (T9.3)

**S9-P4 (standard diagram stability, cited).** On the *same* finite filtered
complex, if \(\|f-g\|_\infty\le\eta\), the full superlevel persistence
diagrams satisfy \(d_B(D(f),D(g))\le\eta\), with essential points matched
separately. **Proof sketch.** Every cell-entry value is a minimum of its
vertex values, a 1-Lipschitz operation in the sup norm. The filtrations are
\(\eta\)-interleaved, and finite-module algebraic stability yields the
bottleneck inequality. A finite bar of lifetime greater than \(2\eta\)
cannot match the diagonal; a matched bar's lifetime changes by at most
\(2\eta\). This is an existing theorem, not a new contribution. Primary
source: Cohen-Steiner, Edelsbrunner & Harer (2007), DOI
[10.1007/s00454-006-1276-5](https://doi.org/10.1007/s00454-006-1276-5).

For positive power and background on **the same sampling grid and mask**,
\(f=\log(P/B)\) and \(g=\log(P'/B')\) obey
\[
 \|f-g\|_\infty\le
 \|\log(P'/P)\|_\infty+\|\log(B'/B)\|_\infty.
\]
This is directly estimable from paired processing branches when the relative
factors stay positive and interpolation itself is controlled. If a sample
crosses a mask or detection threshold, P4 no longer compares the same
complex. Recenter/MAD normalization changes the field and requires its own
verified bound; raw-field stability is not automatically a bound on Stage 8's
normalized, clipped, composite score.

**S9-T1 (new, conditional finite-order ridge-jump proposition; awaiting
independent review).** Suppose frequencies of a *specified target candidate*
\(\nu_n=\nu_0+n\Delta_*+\kappa_n\), for \(n=0,\ldots,N-1\), occupy
**consecutive trial rows** \(q_n=\lfloor\nu_n/\Delta\rfloor\), with
\(q_{n+1}=q_n+1\). Assume all corresponding vertices are observed and each
target is retained among the local-maximum/top-five candidates. Let
\(|\kappa_{n+1}-\kappa_n|\le C\), and let each retained candidate phase be
within \(e\) circular cycles of \(\{\nu_n/\Delta\}\). Set
\(\delta=\operatorname{dist}(\Delta_*/\Delta,\mathbb Z)\),
\(h=C/\Delta+2e\), \(D=(\delta-h)_+\), \(U=\min(1/2,\delta+h)\).
Then for *every* consecutive target pair
\[
 D\le d_\circ(u_{n+1},u_n)\le U.
\]
If \(U\le J\), every target candidate edge passes the frozen graph's **phase
threshold**. If \(D>J\), no such target edge passes. If the graph returns a
contiguous target path of length \(L\ge2\) among \(N\) valid rows, its
coherence is at most \((L/N)\exp(-D/J)\). If \(D>J\), no length-two target
path exists and its hypothetical target-path score is zero. This is **not**
an upper bound on the graph's maximum over competing paths or on the complete
topological score.

**Proof.** Modulo one, the true phase increment is
\(\Delta_*/\Delta+(\kappa_{n+1}-\kappa_n)/\Delta\). Distance to an integer
is 1-Lipschitz, and two localization errors change circular distance by at
most \(2e\). Truncate the upper distance at the circle diameter \(1/2\).
Compare the resulting interval to the inclusive edge threshold. Every jump
of a retained target path is at least \(D\), hence its mean is at least
\(D\); its capped contrast factor is at most 1, giving the score ceiling.

**Scope and physical interpretation.** \(C\) can be bounded from a fixed,
identified mode list or a calibrated curvature simulation; \(e\) includes
half-bin quantization \(1/(2B)\) *only when the relevant peak is actually
detected in that bin*, plus separately calibrated measurement/localization
error. A baseline-error interval for \(\Delta_*\) does not arise from this
inequality alone. The map \(\delta(\Delta)\) aliases, so it is not monotone
in the absolute spacing error. For a finite four-row witness with
\(\Delta_*=78\), \(\Delta=100\), \(C=0\), \(e=1/48\), and phases
\((0.95,0.73,0.51,0.29)\), all physical target frequencies
\((1095,1173,1251,1329)\) occupy adjacent trial rows 10–13.
Here \(D=0.22-1/24\approx0.1783>J\), so the correctly detected
24-bin target candidates have no adjacent graph edges. At
\(\Delta_*=108\), \(\Delta=100\), the corresponding upper phase jump
is \(U=0.08+1/24\approx0.1217<J\) when all rows/candidates are retained.
These are explicit design-region statements, and the unit test exercises
the *actual* Stage 8 candidate graph on both finite fields. At
\(\Delta=\Delta_*/2\) the mismatch map is zero,
**but true radial orders skip trial rows**, defeating the consecutive-row
hypothesis. At \(\Delta=2\Delta_*\), multiple physical orders can share a
trial row, defeating it again. We use these as scope counterexamples, not
claims of half-alias acceptance or double-alias rejection by the actual
Stage 8 graph. Near the nominal spacing, a missing order, crossing mode,
incorrect mode association, or pruned peak also voids graph conclusions.
No universal ridge-persistence-loss monotonicity follows: a frequency shear
can preserve topological lifetimes while changing horizontal phase drift.

## 4. Probabilistic calibration (T9.4)

**S9-P5 (proposition; conditional Gamma/Chernoff union bound).** Under the
raw-bin Gamma marginal model above, for \(x>0\),
\[
 \Pr\{\max_{1\le i\le m}|\log X_i|>x\}
 \le\min\{1,m[e^{-k(e^x-1-x)}+e^{-k(e^{-x}-1+x)}]\}.
\]
**Proof.** Apply the Gamma MGF \((1-t/k)^{-k}\) with optimized positive
and negative Chernoff parameters to the two tails, then union bound over
bins. This calculation needs neither bin independence nor Gaussianity.
Inverting the right side at a preregistered \(\alpha\) supplies a high
probability raw-log-field sup radius. Add a *separately justified*
background log error \(\eta_B\) to obtain an input for P4 on a fixed mask.
The Chernoff radius may be far larger than typical empirical fluctuation;
the experiment reports both coverage and conservatism. A selected maximum
spacing score requires a distinct max-statistic calibration as in Stage 8.

## 5. Stellar propagation and classifications (T9.5, T9.7)

**S9-P6 (conditional exact algebra; scaling laws empirical).** Let positive
errors in \(\Delta\nu,\nu_{\max},T_{\rm eff}\) have absolute logarithmic
allowances \(a,b,t\). Introduce **independent** astrophysical correction
allowances \(c_\Delta,c_\nu\). For the conventional uncorrected scaling
monomials \(\rho\propto\Delta\nu^2\),
\(R\propto\nu_{\max}\Delta\nu^{-2}T^{1/2}\),
\(M\propto\nu_{\max}^3\Delta\nu^{-4}T^{3/2}\), and
\(g\propto\nu_{\max}T^{1/2}\), the respective absolute log-error bounds are
\(2(a+c_\Delta)\), \((b+c_\nu)+2(a+c_\Delta)+t/2\),
\(3(b+c_\nu)+4(a+c_\Delta)+3t/2\), and \((b+c_\nu)+t/2\).
**Proof.** Take logarithms of the monomials and apply the triangle inequality.
Each log bound \(L\) yields exact conditional fractional interval
\([e^{-L}-1,e^L-1]\); the first-order form is the signed log Jacobian for
small allowances. The monomials themselves are empirical approximations:
stellar composition, structural/nonhomology and solar-reference uncertainty
require separate analysis. The function requires both systematic budgets
explicitly; it never treats them as known zero. A Stage 8 alias failure does
not yield a small \(a\), so **no observational stellar error bar is issued**.
Primary motivation for scaling cautions: [Viani et al. (2017)](https://doi.org/10.3847/1538-4357/aa729c).

| ID | Classification | Novelty/qualification |
| --- | --- | --- |
| S9-P1 | Proposition: exact known identity | Ordinary elder-rule prominence; boundary/tie caveats. |
| S9-P2 | Proposition: exact ideal geometry | Finite/noisy samples separately bounded. |
| S9-P3 | Proposition: exact lifted algebra; approximate proxy | Requires identified modes, order lift, spacing agreement. |
| S9-P4 | Cited theorem | Fixed complex and raw-field sup bound only. |
| S9-T1 | **New conditional proposition, proof draft** | Target candidate/adjacent row only; awaits independent review. |
| S9-P5 | Proposition: conditional probabilistic bound | Raw Gamma marginal model; smoothing not covered. |
| S9-P6 | Proposition: exact conditional algebra over empirical scaling | Separate seismic/astrophysical budgets required. |
| S9-E1 | Empirical regression | Monte Carlo conservatism and adversarial examples; no universal guarantee. |
| S9-C1 | Conjecture/open question | No monotone persistence-loss law stated or claimed. |

**Review boundary.** Automated checks can falsify statements but do not
constitute an independent proof review. G9 remains `review_pending` until a
named independent mathematical reviewer verifies S9-T1 and signs the proof
packet. The validation command reports implementation integrity separately
from that acceptance gate.
