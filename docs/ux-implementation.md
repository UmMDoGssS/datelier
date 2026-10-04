# Inspection UX implementation

Started 2026-10-04 from the [Titanic review](ux-titanic-review.md), following its
ordered repair sequence. Existing v1 feature gates remain unchanged. Each
implementation slice is verified and committed before the next one starts.

## Step 1 — Understandable single-column charts (complete)

### 1a — Correct profile coordinates and labels

Committed as `e50de61`.

Implemented real histogram bin edges, named horizontal category bars, formatted
temporal axis ticks, and value-based relationship-grid diagonals. Prepared
arrays remain immutable. Precision-lost bin boundaries are collapsed; constant
and extreme-value profiles retain all finite counts. Histogram outlines close
at zero and temporal plots have enough axis padding for endpoint labels.

Verification:

- Batch Pyrefly: zero errors.
- Focused profiling/exploration/relationships/distributions tests: **22 passed**.
- Ruff lint, format, and diff whitespace checks pass.
- Live `exploration_smoke.py`: 82 frames; profiles, automatic scatter, edit
  invalidation, and source preservation pass.
- Live `relationship_smoke.py`: heatmap/grid rendering and drill-down pass.
- `profile_smoke.py` on Titanic `sex`: 551 male / 299 female, directly labelled
  bars; all 850 counted rows and source preservation verified.
- Titanic age profile: 676 finite values, 174 missing, real age bin boundaries.
- Synthetic date profile: formatted 2024-01-01 through 2024-01-05 endpoint labels
  visually verified. Existing tests cover nanosecond datetime/duration/time
  precision, constants, all-null inputs, overflow, and category overflow.

GUI checks use Linux/Mesa software OpenGL with frame hooks and disabled
preferences. [Category capture](evidence/ux-implementation/category-axes.png),
[temporal capture](evidence/ux-implementation/temporal-axes.png), and their JSON
records preserve the observed counts. The deterministic smoke fixture is
generated temporarily; the Titanic CSV is not committed.

Commands use `UV_CACHE_DIR=/tmp/datelier-uv-cache uv run --offline`; GUI commands
also set `LIBGL_ALWAYS_SOFTWARE=1 POLARS_MAX_THREADS=8`:

```sh
uv run pyrefly check
uv run pytest tests/test_profiling.py tests/test_exploration.py tests/test_relationships.py tests/test_distributions.py
uv run ruff check .
uv run ruff format --check .
uv run scripts/exploration_smoke.py --output /tmp/datelier-ux-axes.ppm
uv run scripts/relationship_smoke.py
uv run scripts/profile_smoke.py --source /home/ummdogsss/Downloads/titanic_train.csv --column sex
uv run scripts/profile_smoke.py --source /home/ummdogsss/Downloads/titanic_train.csv --column age
uv run scripts/profile_smoke.py --column day
```

### 1b — Direct chart switching and compact summaries

The ordinary single-column view now places labelled Column and Chart type
controls above the plot. Numeric columns offer Histogram, KDE, ECDF, Box, and
Violin; categorical columns use named counts and temporal columns use a
formatted histogram. Included and missing counts remain visible, while detailed
statistics, sampling settings, and bin counts sit under a collapsed Details
section. Extreme numeric histograms explicitly label their normalized units.

Curves are prepared on demand in a worker. Revision changes and abandoned jobs
cannot publish stale results. Constants explain unavailable density and suggest
Histogram or ECDF; all-null columns show an empty state without preparing curves.
The selected chart type survives workspace save/restore, and older workspace
recipes default to Histogram.

Verification:

- Batch Pyrefly: zero errors; Ruff lint, format, and diff whitespace checks pass.
- Full pytest suite: **353 passed**. Behavioral coverage includes worker reuse,
  failure recovery, stale-result rejection, abandonment, old workspace recipes,
  and chart-type persistence.
- Live Titanic age KDE and ECDF render 676 included values and 174 missing
  (20.5%); sex counts render 551 male / 299 female. Source hash is unchanged.
- Live single-column Box and Violin render; constant KDE gives its fallback
  message, and all-null ECDF reports 0 included / 5 missing (100%).
- Live `comparison_smoke.py`: all five existing comparison modes and recovery
  pass. `workspace_smoke.py`: save, moved-source relink, restore, saved chart
  type, history/selection, and no implicit ML runs pass.

[Updated category view](evidence/ux-implementation/profile-counts.png),
[Titanic KDE](evidence/ux-implementation/profile-kde.png), and
[Titanic ECDF](evidence/ux-implementation/profile-ecdf.png) record the new controls
and compact summaries. KDE/ECDF JSON records preserve counts and source checks.
GUI evidence uses Linux/Mesa software OpenGL and scripted frame hooks; the
review's pointer-only usability time targets have not yet been measured.

Additional commands (same environment as above):

```sh
uv run pytest
uv run scripts/profile_smoke.py --source /home/ummdogsss/Downloads/titanic_train.csv --column age --mode KDE
uv run scripts/profile_smoke.py --source /home/ummdogsss/Downloads/titanic_train.csv --column age --mode ECDF
uv run scripts/profile_smoke.py --column value --mode Box
uv run scripts/profile_smoke.py --column value --mode Violin
uv run scripts/profile_smoke.py --column constant --mode KDE
uv run scripts/profile_smoke.py --column empty --mode ECDF
uv run scripts/comparison_smoke.py
uv run scripts/workspace_smoke.py
```

Plot sizing, unified analysis, styling, roles/grouping, direct table actions, and
file dialogs remain subsequent steps in the review plan. Step 1's functional and
rendering gate has passed; the broader UX repair sequence remains open.

## Follow-up — Analysis navigation crash (complete)

A real Dear ImGui click on **Analysis inputs**, with no fitted results and the
Analysis panel hidden, reproduced exit 139. Replacing `imgui.set_window_focus`
with Hello ImGui's dock-aware focus API fixes that path and reveals the panel.
This is a panel-navigation failure; a missing fit is a supported state.

`analysis_navigation_smoke.py` passes with both default and hidden Analysis
panels (42 frames each), with no ML started. Sixteen focused analysis-job,
workspace-view, and exploration tests pass; Pyrefly reports zero errors and
Ruff lint/format plus diff whitespace checks pass. Scatter mode separation and
chart sizing remain the next verified slices.

## Follow-up — Contextual scatter and correlation controls (complete)

Scatter has one Coordinates selector. Columns shows manual X/Y and optional Z;
PCA, t-SNE, and UMAP show the selected method's inputs and explicit Run command.
Unfitted methods retain their setup without displaying a raw fallback or
starting ML. Shared feature/preprocessing forms keep the Analysis panel and
inline inputs consistent. Fitted views collapse setup by default, identify
changed inputs, and preserve linked rows and independent raw 2D/3D settings.
One Color selector covers uniform, column, and completed cluster colors.
Manual axes update in the worker when changed; occupied axes swap safely.

Correlations now has a local Features picker, an above-control Chart type
caption, and compact counts. Pair grid is omitted when more than eight features
are present. Detailed explanations are collapsed. Workspace/preferences recipes
save the coordinate source with a backwards-compatible default of Columns;
restoring an unfitted method does not run it.

Verification:

- 62 focused workspace/preferences/exploration/analysis-job/relationship tests
  pass; Pyrefly reports zero errors; Ruff lint/format and diff whitespace pass.
- `scatter_modes_smoke.py` on Titanic verifies the widgets actually rendered
  in each mode, clicks Run PCA, visits unfitted t-SNE/UMAP, and returns to Columns.
  The source hash remains unchanged.
- `analysis_workbench_smoke.py --dimensions 3` passes explicit PCA, linked 3D
  selection, k-means colors on embedding and raw plots, and source preservation.
- `selection_smoke.py` passes linked selection, wheel zoom, middle-button pan,
  and Shift brushing. `relationship_smoke.py` passes heatmap navigation and
  grid highlighting.
- `workspace_smoke.py` passes saved unfitted coordinate-source restoration,
  moved-source relink, history/selection, and zero implicit ML runs.

These are the requested contextual-control repairs within review step 3. The
broader shared-column context, input preview, and default dock-layout redesign
remain open. Fixed/capped plot heights are addressed in the next slice.

## Follow-up — Chart sizing and visible axes (complete)

Profiles, comparisons, 2D/3D scatter, heatmaps, and pair grids now share adaptive
chart space. **Height** supports dragging or typed values; the visible **Plot
height** divider supports vertical dragging. **Auto** restores adaptive height.
**Expand/Restore** retains native plot identity, including 2D axis ranges and
the 3D camera. Minimum readable heights remain, with scrolling for larger grids;
there is no fixed upper chart-height cap. Manual heights for the four chart
contexts round-trip through old-compatible workspace and preference recipes.

**Axes** exposes numeric 2D ranges and Linear/Symmetric log scales, plus Log 10
for positive ranges. Edits validate together and apply for one frame, allowing
continued native pan/zoom. Category coordinates and formatted temporal
coordinates omit numeric editing; heatmaps keep feature axes. Axis edits reset
when the plotted columns/chart type change and are not saved as workspace data.
Point picking now uses actual screen coordinates, retaining correct row links
under nonlinear scales. Grid cells fit on view changes rather than every frame.

Scatter source/color/dimensions controls share a compact row with captions
above. The Analysis panel follows the chosen decomposition, or shows K-means
in Columns mode; K-means omits unrelated output dimensions. This removes the
remaining competing decomposition controls from the manual-coordinate view.

Verification:

- Full suite: **365 passed**; batch Pyrefly reports zero errors; Ruff lint,
  format, and diff whitespace checks pass.
- `plot_area_smoke.py`: real drag/expand events pass independently for Profile,
  Comparison, Scatter, Scatter3D, Heatmap, and Grid. Grid checks inspect actual
  cell ranges; 3D checks inspect native camera rotation and coordinate ranges.
- Titanic Scatter passes at **1024×768, 1280×800, and 1600×1000**. Expanded plots
  exceed 340 px height. Actual Axes/Apply ranges clicks pass, with subsequent
  wheel zoom and preserved ranges on return.
- `selection_smoke.py --nonlinear` passes sorted/filtered/sampled identity,
  plot/table links, wheel zoom, pan, and brushing under Log 10/Symmetric log.
- `workspace_smoke.py` passes all four saved heights, unfitted coordinate
  source, missing-source relink, history/selection, and no implicit ML runs.
- Final analysis navigation, exclusive-mode, 3D PCA/k-means/linked selection,
  and correlation drill-down regressions pass. `relationship_smoke.py --wide`
  verifies that a twelve-feature view offers Heatmap only.
- Titanic SHA-256 remains
  `ae179070a631b75d2c3fc7439d624c7fb5e0c8859919dc1d4f96d4d3ed6e854b`.

[PCA controls](evidence/ux-implementation/contextual-pca.png),
[correlation controls](evidence/ux-implementation/contextual-heatmap.png), and
[expanded numeric scatter](evidence/ux-implementation/expanded-scatter.png)
record the new surfaces. JSON records retain the input-event gates and source
checks. GUI verification remains Linux/Mesa software OpenGL, using Dear ImGui
input events and scripted frame hooks. Numeric setup follows the installed
bindings and [ImPlot's setup contract](https://github.com/epezent/implot/blob/master/implot.h).

The user's reported crash, conflicting coordinate controls, and missing sizing/
axis controls are repaired. The review's broader Table focus action, shared
column context, pre-fit input preview, full layout/hierarchy redesign, and
pointer-only usability timings remain open; these functional checks do not
claim completion of every original UX acceptance target.

## Follow-up — 3D faces and relationship readability (in progress)

Three bounded slices follow the user's next inspection request:

1. Add six face presets and an isometric view to raw and reduced 3D scatter.
   Apply orientation once, preserving ranges, linked selections, and subsequent
   camera gestures. Verify real menu clicks, face geometry, and expand/restore.
2. Annotate heatmap cells, including undefined values, and replace the scale
   subtitle with a matching Pearson color bar. Verify cell ordering, navigation,
   undefined rendering, and narrow/expanded layouts.
3. Replace dense pair-grid feature indices with names on the outer axes.
   Verify five-to-eight-feature labels and existing linked selection/navigation.

Each slice requires focused tests, batch Pyrefly, Ruff, GUI verification, and
a separate commit. The final slice also requires the full test suite.

### 3D viewing faces (complete)

Raw and reduced 3D scatters expose **View face** with six named faces and an
isometric orientation. Presets preserve ranges and linked selection, including
expanded views. The camera updates for one frame; subsequent rotation is free.
Face-menu clicks are consumed before plot picking/gestures. Camera orientation
remains session state, consistent with existing native camera gestures.

The installed renderer uses **right-drag to rotate, left-drag to pan**. Previous
UI text had these reversed; it is corrected. The older smoke's point-position
checks did not distinguish rotation from pan. It now verifies actual native
quaternions and ranges as well as projected picking/brushing.

Verification: eleven focused plot-data/selection/3D tests pass; Pyrefly reports
zero errors; Ruff lint/format and diff whitespace pass. Real face-menu clicks
pass on Titanic (321 frames) and explicit 3D PCA (386 frames), testing all seven
presets, expected projected planes, free rotation, expanded-menu use, stable
ranges, selection, and source hashes. The strengthened 3D gesture smoke passes
(141 frames). Checks use Linux/Mesa software OpenGL. API behavior was checked
against installed bindings and [ImPlot3D's rotation setup contract](https://github.com/brenocq/implot3d/blob/main/implot3d.cpp).
The remaining two relationship-readability slices are open.
