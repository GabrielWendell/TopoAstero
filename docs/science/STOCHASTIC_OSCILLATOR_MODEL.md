# Stochastic oscillator and observation model

## Mean spectrum

Each mode is represented by a height-parameterized Lorentzian

$$
S_k(\nu)=\frac{H_k}{1+4(\nu-\nu_k)^2/\Gamma_k^2},
\qquad
\Gamma_k=\frac{10^6}{\pi\tau_k(86400)}\;\mu\mathrm{Hz}.
$$

Here $H_k$ is the mode height, $\Gamma_k$ is the FWHM, and $\tau_k$ is the damping lifetime in
days. The background is white noise plus registered Harvey-like components,

$$
B(\nu)=W+\sum_j\frac{A_j}{1+(\nu/\nu_j)^{p_j}}.
$$

The simulator includes degree visibility and optional equal-height rotational components. Its
compact asymptotic comb is an experiment generator, not a precision stellar-structure model.

## Stochastic realizations

For an uninterrupted Gaussian stationary process, each independent raw periodogram ordinate is
drawn as

$$
I(\nu_i)\sim \operatorname{Exponential}(S(\nu_i)).
$$

The time-domain generator draws Hermitian Fourier coefficients with the variance required by the
TopoAstero one-sided PSD convention, then applies an inverse real FFT. Ensemble mean, ordinate mean
and variance, and Parseval-consistent time variance are regression-tested.

## Observation operator

An exposure of duration $\Delta t$ attenuates stellar power by

$$
R(\nu)=\operatorname{sinc}^2(\nu\Delta t).
$$

Contamination fraction $c$ dilutes stellar variability by $(1-c)^2$ while the separately specified
instrumental white-noise level is not diluted. Duration fixes the Fourier resolution; cadence fixes
the Nyquist frequency and integration response. Gaps are either random thinning or masks generated
from compact observing intervals.

The real-window templates use finite PDCSAP timestamps from payload-verified Kepler Q5 and TESS
sector 14 files. Quality screening remains a pipeline choice so the template represents data
availability rather than one particular cleaning branch. The interval table retains product keys
and source SHA-256 values; raw mission payloads are not redistributed.

## Scope and limitations

- Frequency-bin independence is exact only for the ideal uninterrupted Gaussian model.
- A finite or gapped series couples frequencies through its spectral window.
- The equal-height rotational prescription omits inclination-dependent $m$ visibilities.
- The compact asymptotic comb omits mixed-mode coupling and detailed structural glitches.
- Harvey components are phenomenological nuisance models.
- Any representation that fails family-specific null calibration is diagnostic-only or dropped.
