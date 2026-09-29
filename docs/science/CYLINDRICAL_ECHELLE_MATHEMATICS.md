# Cylindrical topological echelle: mathematical object and limits

Stage 8 evaluates a frequency density on (I\times S^1), not an image with two unrelated
vertical borders. For a trial large spacing \(\Delta>0\), order \(q=\lfloor\nu/\Delta\rfloor\), and
normalized angle \(u=\theta/(2\pi)\in[0,1)\), the sampled field is

\[
E_\Delta(q,u_j)=\log\left[P\{\Delta(q+u_j)\}/B\{\Delta(q+u_j)\}\right],
\qquad u_j=(j+1/2)/24.
\]

The angular endpoint is **not** duplicated: \((q,23)\) is adjacent to \((q,0)\). Vertical
edges join adjacent orders only; there is no radial wrap. The positive PSD and fitted
background are interpolated only inside their measured frequency interval. Every partially
observed order is retained as a mask. Orders with less than 75% angular coverage have no
vertices, and every other missing vertex removes all incident cells. A missing bin is never
encoded as a low observation. This gives a subcomplex of the finite cylinder. Isolated
incomplete orders can create extra essential components; these are kept but excluded from
numeric persistence summaries.

Each square contains its four vertices, four boundary edges, and one 2-cell; a seam square
uses columns 23 and 0. The superlevel upper-star complex at level \(t\) contains a cell
when **all** its vertices have \(E\geq t\), so its entry level is the minimum vertex field
value. Coefficients are \(\mathbb F_2\). This is genuinely cubical, whereas the older Stage 5
periodic-grid backend triangulates squares; the two implementations have deliberately
separate identities. Both \(H_0\) and \(H_1\) are computed by exact boundary reduction
for bounded figures and tests. The scan uses an independent union-find \(H_0\) reduction
on the identical vertices and edges, cross-checked against the full diagram. A filled
constant cylinder has one essential \(H_0\) and one essential \(H_1\); the same rectangular
complex has one essential \(H_0\) and no essential \(H_1\).

For the registered score, the observed log-ratio field is centered by its global median
and divided by \(\max(0.5,1.4826\operatorname{MAD})\) over valid vertices. The raw log(P/B)
field remains available for display. Let \(L_i\) be *finite* normalized \(H_0\) lifetimes,
\(N\) the number of nonempty orders, and \(C\) the best seam-aware adjacent-order ridge
coherence. Then

\[
H=\frac{1}{12N}\sum_{i=1}^{3N}\min(L_{(i)},4),\qquad
T(\Delta)=0.55H+0.45C.
\]

The ridge graph starts at circular local maxima, keeps at most five candidates per
order, connects consecutive orders within 0.17 cycles, and scores up to three
competing paths with length, circular jumps, and capped contrast. Its \(C\) alone is a
topology-free ablation. The per-order periodic \(H_0\) maximum is an orderwise
diagnostic, **not** an exact zigzag persistence implementation; no zigzag theorem or
claim is attached to that table. Finite \(H_1\) and the essential cylinder cycle are
localized and audited, not opportunistically inserted into \(T\).

Given a correctly identified radial ridge center \(u_0\) and quadrupole center \(u_2\),
the angular small-separation proxy is \(r_{02}^{\rm angle}=(u_0-u_2)\bmod 1\), with
\(\Delta\theta_{02}=2\pi r_{02}^{\rm angle}\). The proxy is not a substitute for
five-point \(r_{01}\) or \(r_{10}\). The latter require an externally identified,
order-indexed mode-frequency list and use the standard five-point numerator divided
by the corresponding \(\ell=1\) or \(\ell=0\) large separation. Unlabeled or overlapping
ridge hypotheses return missing angular quantities. The published KIC 10963065 mode
and ratio tables serve only an independent formula audit; published ratio point
estimates need not equal ratios of rounded point-frequency estimates exactly.

Interpretation is bounded to the simulation and sampling regime in
`configs/stage8_echelle.yaml`. A correct periodic domain is a mathematical result,
not proof that a combined topological score improves large-separation inference.
