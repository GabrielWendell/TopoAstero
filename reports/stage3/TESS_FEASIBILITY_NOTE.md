# TESS feasibility and combination decision

Eleven SPOC two-minute sectors were analyzed independently. Their 24.98-28.20-day baselines give
0.410-0.463-uHz Rayleigh resolution, which nominally resolves a 103-uHz separation, but the
single-sector envelope/comb evidence is unstable.

Sector 15 alone meets all four frozen marginal criteria (`numax=2132.01 uHz`, envelope ratio
1.221, `dnu=107.77 uHz`, ACF peak 0.109). It is labeled
`marginal_candidate_not_confirmation`. Ten sectors fail at least one criterion and remain explicit
non-detections. Sectors with envelope ratios above 1.20 but incompatible centers/spacings are not
rescued after inspection.

**Decision:** do not combine sectors for a Stage 3 detection. Combining separated sectors can
improve nominal resolution while imposing a complicated spectral window and mixing epochs. A later
transfer analysis may combine only predeclared homogeneous SPOC/cadence products with an explicit
window likelihood and must report the individual-sector failures alongside any aggregate result.

The full sector table is `results/stage3/tess_sector_feasibility.csv`; the figure is
`reports/stage3/figures/tess_sector_feasibility.svg`.
