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
- [ ] All-plot legend audit, native categorical/cluster entries, continuous
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
