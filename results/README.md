# Results policy

Commit only compact, machine-readable reference outputs, figure recipes, and release tables.
Large or reproducible intermediates belong in the derived tier and are archived only when their
regeneration cost or scientific value justifies it.

`stage3/` contains compact machine-readable outputs from the checksum-verified Rudy classical run:
baseline and convention tables, background/window/echelle/mode evidence, preprocessing and
uncertainty sensitivity, a reduced figure-source spectrum, TESS sector results, and the run manifest.

`stage4/` contains compact analytic regressions, simulator recovery evidence, the complete pilot
map, independent null/multiplicity calibration, uncertainty coverage, compute/precision budgets,
figure-source excerpts, and the sealed Stage 4 run manifest.

`stage5/` contains backend cross-checks, the 72-cell five-representation feature panel, localized
pairs, independent representation null calibration, nuisance sensitivities, redundancy and
conditional-ablation tables, locked selection scores, environment identity, and the sealed Stage 5
run manifest. These are development-only selection artifacts, not population performance results.
