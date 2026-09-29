# Delay-embedding topology and the phase-information question

## Scientific question

Stage 7 asks whether the topology of a time-delay point cloud contains information about mode
coherence, damping, lifetime, or phase organization that is not already fixed by the power
spectral density (PSD). The test is deliberately able to return a negative answer.

For a scalar series \(x_t\), the registered embedding is

\[
X_t=(x_t,x_{t+\tau},\ldots,x_{t+(m-1)\tau}).
\]

Only windows for which every coordinate is observed and finite enter the cloud. The primary
dimension is \(m=3\); \(m=4\) is used only for a bounded \(H_2\) diagnostic. Robust centering and
scaling occur before window construction. Deterministic farthest-point sampling controls density
without silently interpolating gaps.

## Delay policy

Four delay rules are compared on simulations only: one quarter of the physics-informed mode
period, the first autocorrelation minimum, the first normalized mutual-information minimum, and a
multiscale consensus. The consensus is frozen as primary. Population data cannot retune it.

## Persistence and metric audit

Vietoris--Rips persistence is computed directly on the unreduced delay cloud with coefficients in
\(\mathbb F_2\). PCA is visualization-only. The primary Euclidean metric is compared with
standardized Euclidean and cosine-chord sensitivities, and convergence is evaluated under landmark
subsampling. Essential classes retain localization but receive no artificial death or finite
summary value.

## PSD-preserving falsification

Phase-randomized surrogates preserve Fourier amplitudes exactly. IAAFT surrogates additionally
preserve the empirical amplitude distribution approximately while iterating toward the target PSD.
For every signal and null family, the largest registered \(H_1\) score across all four delay rules
is tested with a paired plus-one empirical p-value. This maximum-statistic construction accounts
for the within-signal delay search; Benjamini--Hochberg controls the across-cell exploratory map.

## Classical controls and decision

The same calibration/evaluation split is used for autocorrelation coherence time and integral,
wavelet concentration, spectral entropy, dominant Fourier fraction, and a Fourier phase-coupling
summary. Delay topology is retained only if it reproducibly rejects both PSD-preserving null
families or improves held-out lifetime prediction over these controls by at least the frozen
margin. Otherwise the negative result is frozen and delay PH leaves the project critical path.

