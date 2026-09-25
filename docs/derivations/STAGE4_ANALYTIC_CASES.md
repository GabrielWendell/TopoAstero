# Stage 4 analytic cases

This note fixes the exact cases used to interpret later topological summaries. Frequencies are in
microhertz and time is in days unless stated otherwise. Numerical evidence is in
`results/stage4/analytic_cases.csv`; executable counterparts are in
`tests/unit/test_simulation_lab.py`.

## One-dimensional peaks: persistence and prominence

Let a finite scalar signal be a function on the vertices of a path graph. Insert vertices in
descending value and join adjacent active components. Under the elder rule, when components born
at peaks $p_i$ and $p_j$ merge at a saddle $s$, the younger component dies and its finite
zero-dimensional superlevel persistence is

$$
\pi(p)=f(p)-f(s).
$$

Classical peak prominence is the vertical distance from the peak to the highest contour that
connects it to a higher peak. On a path this contour is precisely the elder-rule merge saddle, so
prominence equals finite $H_0$ persistence.

The equivalence requires: a path graph, a superlevel filtration, identical tie handling, an
interior non-global peak, and the same boundary convention. The surviving global class is
essential and has no finite prominence partner. Boundary-reaching peaks and zero-length bars are
excluded. The claim is not extended to higher-dimensional domains or other filtrations.

## Sinusoidal delay ellipse

For $x(t)=A\cos\theta$ and delay phase $\phi$, put $X=x(t)$ and
$Y=x(t+\tau)=A\cos(\theta+\phi)$. Eliminating $\theta$ gives

$$
X^2+Y^2-2\cos(\phi)XY=A^2\sin^2(\phi).
$$

Rotating to $(X+Y)/\sqrt2$ and $(X-Y)/\sqrt2$ gives semiaxes

$$
a=A\sqrt{1+|\cos\phi|},\qquad b=A\sqrt{1-|\cos\phi|}.
$$

The curve degenerates to a line for $\phi=0\pmod\pi$ and becomes a circle for
$\phi=\pi/2\pmod\pi$. A two-sinusoid signal generally fills a two-dimensional region rather than
one exact conic; Stage 4 therefore treats the single-mode ellipse as a regression, not as a
universal physical model.

## Exact finite comb and aliases

For frequencies $\nu_n=\nu_0+n\Delta$, folding modulo the true $\Delta$ produces one ridge.
Folding modulo $\Delta/2$ also produces one ridge, establishing the half-spacing alias. Folding
modulo $2\Delta$ separates even and odd orders into two ridges. These statements require an exact
comb and exact arithmetic; curvature, mixed degree, rotation, finite linewidth, and missing orders
broaden or split the ridges.

## Ridge mismatch

For $N$ consecutive centered orders and a trial-spacing error $\epsilon$, the unwrapped
displacement is $n\epsilon$. Therefore

$$
\operatorname{RMS}=|\epsilon|\sqrt{\frac{N^2-1}{12}}.
$$

The result assumes centered consecutive integer orders and no phase wrap. A quadratic curved ridge
$c n^2$ instead has RMS $|c|\sqrt{N^{-1}\sum n^4}$; it cannot be absorbed into a constant spacing
without residual structure.

## Peak profiles

The Gaussian $\exp[-x^2/(2\sigma^2)]$ reaches half height at
$|x|=\sigma\sqrt{2\log2}$. The Lorentzian $[1+(x/\gamma)^2]^{-1}$ reaches half height at
$|x|=\gamma$. These cases freeze the width conventions used by the simulator.

## Interpretation boundary

Passing an exact case shows that an implementation respects its mathematical convention. It does
not establish power, calibration, robustness to nuisance structure, or astrophysical validity.
Those properties are evaluated separately by the stochastic, null, and observation-model parts of
Stage 4.
