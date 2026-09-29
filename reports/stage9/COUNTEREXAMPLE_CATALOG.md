# D9.3: counterexamples and assumption violations

Each construction has machine-readable parameters in
`results/stage9/counterexamples.json`; it is a failure mode, not a successful
spacing detection.

| ID | Construction | Defeated inference |
| --- | --- | --- |
| CE01 | Two strict maxima joined by a valley; raise the valley to the lower peak. | Two positive finite bars can merge into a zero bar; count is not stable without persistence margin. P1 requires distinct heights for the simple strict-max formula. |
| CE02 | An endpoint peak is born at the first vertex, and the global maximum is essential. | Discarding edges or assigning finite lifetime to the survivor changes the identity. |
| CE03 | One target ridge row is absent between two observed rows. | The Stage 8 graph only connects adjacent trial rows; small phase jump across the gap does not create an edge. |
| CE04 | Quadratic frequency residual \(\kappa_n=c(n-n_0)^2\) makes local increments vary. | A bound with \(C=0\) fails; fit a finite-range \(C=\max|\kappa_{n+1}-\kappa_n|\), and do not extrapolate outside it. |
| CE05 | Two ridges cross, with an alternative brighter candidate at the crossing. | T1 bounds a specified target track, not the graph's selected global winner or its mode identity. |
| CE06 | A comb folded with both \(\Delta_*\) and \(\Delta_*/2\) has zero circular phase drift. | Phase drift alone cannot identify the fundamental; half alias skips trial rows. The double alias can collide within rows. |
| CE07 | Two commensurate combs, one at \(\Delta_1\), one at \(\Delta_2\), coexist. | A spacing response may have multiple maxima; a unimodal interval is not justified by a stability theorem. |
| CE08 | Two seeded Gamma realizations with identical marginal spectrum reorder two nearly tied peaks. | Small model-average variance need not preserve peak ranking in each draw, and a raw-bin Gamma bound does not cover smoothed/selected maxima. |
| CE09 | Horizontal shear of an ideal cylinder changes a ridge's angular slope while preserving its field-value multiset; a coherent homeomorphic remapping can preserve its persistence diagram. | Bottleneck stability does not imply strictly monotone persistence loss under spacing mismatch. |

The catalog intentionally does not assert that Stage 8's actual combined score
attains equal maxima at every geometric alias. It reports geometry and failure
of stated assumptions. Mask changes, ties, altered normalization, changed
sampling positions, and astrophysical model discrepancies require separate
analysis.

