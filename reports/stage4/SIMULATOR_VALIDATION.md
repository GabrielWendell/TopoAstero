# Stage 4 simulator validation

The registered Lorentzian-height/FWHM oscillator simulator passed the ensemble PSD, exponential-ordinate, time-domain variance, frequency, height, and linewidth checks. The validation uses 256 independent spectra and 32 independent time-domain realizations; the exact results are in `results/stage4/simulator_validation.csv` and `mode_recovery.csv`.

Cadence integration uses the squared boxcar response, stellar contamination is a power dilution, and all units are explicit. Mission gaps are reconstructed from payload-verified Kepler Q5 and TESS sector 14 timestamps rather than invented masks.
