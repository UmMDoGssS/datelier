# Scatter views and plot legends

The user requested separate 2D/3D scatter charts, automatic two/three components
for coordinate reductions, column axes beneath Coordinates, and native plot
legends throughout inspection instead of legacy text keys.

Deliver in two verified steps:

1. Separate Scatter 2D/3D choices and plot areas, synchronize every reduction's
   output with the selected chart, nest raw axis selectors under Coordinates,
   and preserve saved views and independent heights. Mismatched fitted outputs
   require an explicit rerun; selecting a chart or method never starts ML.
2. Audit every plot family. Replace scatter text keys with native category and
   cluster legends and continuous color scales. Keep named groups, missing/
   Other/noise/unassigned values, opaque colors, and source-linked selections.

## Gates

- [x] Scatter choices, component synchronization, nested controls, raw/reduced
  2D/3D rendering, saved settings, focused tests, Pyrefly, Ruff and GUI pass.
- [x] All-plot legend audit, native categorical/cluster entries, continuous
  scales, linked interactions, full tests and native Titanic verification pass.

Original Titanic usability gates remain separate.

## Scatter step evidence

The chart picker offers Scatter 2D and Scatter 3D. Columns shows X/Y (and Z in
3D) below Coordinates in its own cell; Color column stays below Colors in the
adjacent cell. The editable Dimensions/Output dimensions dropdowns are replaced
by the chosen chart and a fixed Components value. Every reduction uses that
value in both the inline setup and Analysis panel. Switching a chart or method
never runs analysis; mismatched fitted results are withheld until explicitly
rerun. Each scatter chart has its own plot area/height, while the 3D camera stays
with its plot. Old raw XYZ and saved embedding dimensions remain readable.

- 77 focused scatter/control/workspace/preference/category tests pass.
- `scripts/scatter_dimensions_smoke.py` passes 371 native Titanic frames: real
  clicks choose PCA and Scatter 3D and explicitly run PCA with two then three
  components. A two-component result never renders in the 3D chart. Nested axes,
  hidden editable dimensions, all-method request dimensions and independent
  220/260 px heights pass. Reopening preferences restores both heights and 2D
  with zero automatic analysis runs. Source bytes are unchanged.
- `scripts/plot_area_smoke.py --view Scatter3D --source ...` passes 90 native
  Titanic frames: a real height drag and expanded view preserve camera/bounds
  in the independent 3D area.
- Pyrefly reports zero errors, with the existing SciPy warning/HDBSCAN stub
  suppression. Ruff lint/format pass (204 files).

## Legend step evidence

Color workers now prepare nonempty native series aligned with displayed source
rows. Raw and reduced Scatter 2D/3D use clickable category/cluster entries,
including Other, missing, noise and unassigned/excluded groups when present.
Continuous numeric/temporal colors use a native scale beside the canvas; constant
values use one named entry. Extreme spans use a labeled divisor to keep ticks
finite. The 3D scale matches the canvas after the face control takes its space.
The legacy text legend is removed; sampling/provenance notes stay in Details.

Hiding a scatter entry hides both its points and selection overlay, and excludes
it from picking/brushing without discarding source-table selections. An entry
remains available when all its rows are selected. Legend clicks cannot select
points or grouped bars behind them. Box/violin outliers follow their main entry,
and single numeric profiles retain a legend so hidden entries can be restored.

All plot families were audited:

| Plot family | Identification |
| --- | --- |
| Numeric Profiles: Histogram/KDE/ECDF/Box/Violin | Native column legends; statistics use the same colors. |
| Categorical counts and temporal Profiles | Named category/date axes and column title, without a separate text color key. |
| Category–numeric Box/Violin | Category names on native ticks. |
| Category–category grouped bars | Native group legends; hidden groups cannot be picked. |
| Scatter 2D/3D, raw and reduced | Native category/cluster legends or continuous color scale. |
| Pearson heatmap | Native Pearson r color bar and annotated cells. |
| Pair grid, all five diagonals | Native feature axes and per-cell names, without numbered text keys. |
| Synthetic feasibility scatter | Existing native Synthetic rows entry. |

Verification on Linux with Mesa software OpenGL:

- 35 focused coloring/density/selection/scatter/distribution tests pass.
- The full suite passes 493 tests. Pyrefly reports zero errors with the existing
  SciPy warning/HDBSCAN stub suppression. Ruff lint/format pass (208 files).
- `scripts/scatter_legends_smoke.py` checks real native legend clicks in both
  dimensions, raw categorical colors, explicit K-means colors, explicitly fitted
  PCA with the same cluster legends, neutral excluded rows and continuous Age
  color bars. All-selected entries stay clickable, hidden highlights disappear,
  source selections survive, and the bar matches the native canvas height.
  Final runs pass 248 frames in 2D and 256 frames in 3D.
- `scripts/profile_legends_smoke.py` passes 161 Titanic frames: all five numeric
  modes, real hide/restore clicks, coupled box outliers and a single-column legend.
- `scripts/profile_smoke.py` renders 25 plot frames each for Titanic Sex counts
  and a deterministic date fixture, with named category/formatted date axes and
  unchanged source bytes.
- `scripts/category_charts_smoke.py` passes 204 Titanic frames: named box/violin
  categories, grouped bars and linked selections.
- `scripts/pair_diagonal_smoke.py` passes 145 Titanic frames plus 24 after workspace
  reopen: all five diagonals, heatmap controls and zero implicit analysis runs.
- `scripts/pair_grid_labels_smoke.py --source ...` passes 74 Titanic frames:
  native feature names, zoom, expanded-view bounds and linked highlights.
- `scripts/heatmap_labels_smoke.py --source ... --expanded` passes 48 Titanic
  frames: two-decimal cell labels and the matching native −1/+1 Pearson scale.
- `scripts/scatter_modes_smoke.py --source ...` passes 172 Titanic frames: raw/
  reduced rendering, exclusive unfitted controls and explicit PCA execution.
- `scripts/scatter3d_smoke.py` passes 141 deterministic fixture frames: sorted
  source identity, picking, brushing, free rotation, zoom and pan. Its gesture
  fixture uses the independent expanded 3D area so targets stay visible.
- `scripts/scatter_faces_smoke.py --source ... --embedding` passes 390 Titanic
  frames: explicit three-component PCA, all seven native face choices, correct
  projected planes/directions, free rotation, restore and preserved selections.

Titanic source bytes remain unchanged (850 rows, 15 columns), SHA-256
`ae179070a631b75d2c3fc7439d624c7fb5e0c8859919dc1d4f96d4d3ed6e854b`.
