# D9.4: from input perturbations to seismic and stellar quantities

The valid chain is conditional:

1. On common positive PSD/background samples, establish separately
   \(a_P=\|\log(P'/P)\|_\infty\) and
   \(a_B=\|\log(B'/B)\|_\infty\). Then raw log-ratio field error is at most
   \(\eta=a_P+a_B\). Different interpolation grids and changed masks need
   independent comparison and may invalidate a fixed-domain theorem.
2. On the identical finite filtered complex, finite persistence bottleneck
   distance is at most \(\eta\), while each paired essential birth changes
   by at most \(\eta\). Lifetimes above \(2\eta\) cannot disappear into the
   diagonal. This **does not** bound the argmax of a spacing scan, which can
   jump between aliases when score margins are small.
3. If independent evidence gives logarithmic estimator errors
   \(a=|\log(\widehat{\Delta\nu}/\Delta\nu)|\),
   \(b=|\log(\widehat{\nu_{\max}}/\nu_{\max})|\), and a temperature budget
   \(t\), supply *separate* structure/composition/solar-reference allowances
   \(c_\Delta,c_\nu\). The code requires them as keyword arguments.
4. Conditional algebra then gives log budgets
   \(L_\rho=2(a+c_\Delta)\),
   \(L_R=(b+c_\nu)+2(a+c_\Delta)+t/2\),
   \(L_M=3(b+c_\nu)+4(a+c_\Delta)+3t/2\), and
   \(L_g=(b+c_\nu)+t/2\). Relative intervals are
   \([e^{-L}-1,e^L-1]\), retaining asymmetry for large errors.

For **illustration only**, set \((a,b,t)=(0.02,0.03,0.01)\) and
\((c_\Delta,c_\nu)=(0.04,0.05)\). Log budgets are 0.12, 0.205,
0.495, and 0.085 in the order above. These are assumed inputs, not measured
coverage or observed-star claims. Reporting only the first-order signed
Jacobian at a half/double alias would be materially misleading.

The Stage 8 candidate had alias accuracy 0.2 versus graph-only 0.6 and
90% interval coverage 0.2 on its five detectable evaluation cells. It was
retained for correct cylinder geometry only. No calibrated small \(a\) is
available for it and no physical density, radius, mass, or gravity intervals
follow from this Stage 9 audit. Gamma/Chernoff raw-bin radii are often loose;
simulation-based nuisance calibration and a max-statistic scan remain
necessary for future estimator development.

