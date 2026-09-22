# Localization and interpretation contract

Persistence pairs are scientific objects only when their generating locations remain visible.
TopoAstero therefore stores vertex metadata inside every `TopologicalPair`; plotting code consumes
the same records written to the governed localization catalog.

| Representation | Birth localization | Death localization | Interpretation limit |
| --- | --- | --- | --- |
| Light curve | sample and time of excursion maximum | merge sample/time | morphology only; not a mode-frequency estimate |
| Delay embedding | source sample and landmark coordinates | edge/triangle landmarks | loop persistence is not phase sensitivity until surrogate rejection |
| PSD | birth frequency and normalized log power | merge-saddle frequency | H0 lifetime may equal a prominence under the registered boundary convention |
| Mode cloud | mode frequency, degree, order coordinate | connecting edge/triangle modes | depends on upstream mode extraction |
| Cylindrical echelle | pixel, radial-order coordinate, circular phase | merging pixels | seam-crossing vertices are adjacent; plotted image edges are identified |

Essential classes are shown in diagnostics but carry no artificial finite death. Consequently,
they are not assigned a capped lifetime and never enter totals, centroids, distances, p-values, or
models. This prevents an arbitrary filtration endpoint from becoming a scientific feature.

The Stage 5 localization atlas is generated from `results/stage5/localization_catalog.json` and
uses the project-wide `TA-PLOT-1.0` style. Its annotations are examples from simulation-development
data, not detections in a star.

