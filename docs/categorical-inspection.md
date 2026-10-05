# Column roles and categorical relationships

The October 2026 follow-up is authorized to broaden Scatter beyond numeric
coordinates and make pair-grid diagonals configurable. Deliver in three steps:

1. Infer roles from types and exact non-null uniqueness in data workers. Unique
   strings are Text; repeated strings are Categorical. Explicit Enum/Categorical
   types stay categorical. Unique integers with ID/index names are Identifier;
   uniqueness alone never excludes a numeric measurement. Schema overrides are
   replayable operations, preserved by undo/redo and workspace recipes. Text and
   identifiers remain in the table/export, but leave automatic profiles, numeric
   feature and color pickers. Focused profiles explain their exclusion.
2. Rename Scatter to Relationships and add categorical counts, category/numeric
   aggregation bars and grouped categorical counts with actual category labels.
   Show only controls applicable to the representation. Preserve numeric 2D/3D,
   decomposition, Colors, plot sizing, and linked selection.
3. Add Histogram/KDE/ECDF/Box/Violin diagonal representation to the correlation
   pair grid, with prepared worker data, saved settings, and named axes.

## Verification gates

- [x] Role inference, reversible overrides, workspace replay, and native Schema
  selection pass. ID heuristics are deliberately conservative; inspect the role
  and override Numeric for an ID-like feature or Identifier for an unnamed ID.
- [x] Categorical chart preparation and native conditional controls pass,
  including missing values, numeric finite-value exclusion, bounded categories,
  aggregation, and workspace restore.
- [x] Pair-grid representation preparation, native rendering and saved settings
  pass, with histograms retaining their complete finite-value counts.
- [x] Full suite, Pyrefly, Ruff lint/format, Titanic GUI and source preservation
  checks pass. No analysis is implicitly launched.

The Titanic source has 850 rows. Its `name` column has 849 distinct non-null
values, so the exact all-unique rule keeps it categorical; use a Text override
if those nearly unique names should be excluded too. Numeric category overrides
allow codes such as `pclass` or `survived` to be represented as categories.

Step 1 evidence: 72 focused tests passed; Pyrefly reported zero errors (the
existing dependency stub suppression remains); Ruff lint and format passed.
`scripts/column_roles_smoke.py` clicked the native passenger ID role dropdown,
selected Numeric and undid it in 61 frames. Feature choices updated, no ML ran,
and the Titanic source SHA-256 stayed unchanged.

Step 2 evidence: 60 focused tests passed, including category aggregates, bounded
selection, missing/Other groups, extreme numeric means and workspace replay.
Pyrefly and Ruff lint/format passed. The native Titanic category smoke clicked
Count bars, selected 551 male source rows, rendered mean survival by sex and
grouped embarkation counts with the missing group, and verified exclusive
controls in 120 frames. The numeric scatter/PCA smoke passed in 149 frames.
Grouped legends sit above bars; category/value controls share a row. All runs
preserved the source; category charts launched no ML. Legacy Scatter recipes
open Relationships. Category counts use at most 100,000 input rows, 30 visible
categories plus Other, five groups plus Other, and 10,000 selected IDs per bar.

Step 3 evidence: 31 focused tests and the full 457-test suite passed. Pyrefly
reported zero errors; Ruff lint/format and diff whitespace checks passed.
`scripts/pair_diagonal_smoke.py` clicked KDE in the native dropdown, rendered all
five representations, confirmed the heatmap hides the diagonal control, saved
Violin and reopened the workspace (145/22 frames on Titanic; 143/21 on a
constant-column fixture). Constant KDE cells show No density; constant violin
cells show their box with an explicit fallback label. Invalid distribution
ranges stay local to their diagonal and have an explanatory hover message.
Histogram and box statistics retain all finite values; KDE/ECDF/violin curves
use up to 2,000 values per feature with the saved comparison seed/bandwidth.
Each feature has its own distribution range. Smaller grids now reserve 160 px
per row of cells; large grids retain their bounded, named, scrollable canvas.

Compatibility checks: native Titanic 3D face navigation passed (320 frames),
dense pair-grid names/zoom/selection passed (74 frames), and annotated heatmap
values/color scale passed. Fresh-process preferences save/default/reopen checks
passed, including the Relationships name and legacy view migration. Every
Titanic GUI run preserved SHA-256
`ae179070a631b75d2c3fc7439d624c7fb5e0c8859919dc1d4f96d4d3ed6e854b`.
No ML ran during chart choices or workspace restore. These GUI checks used
Mesa software OpenGL on the reference Linux machine. A text/ID-only fixture
rendered the excluded-analysis state in 18 frames with no plots or ML runs.

Responsibility review: categorical preparation and rendering, role inference,
and pair-diagonal rendering each have separate modules. PlotControls remains
the single owner of plot recipes and bound column choices; ExplorationView
coordinates the tabs and their navigation. Their shared settings are retained
there to keep workspace capture/restore consistent.

## Using the controls

- In Schema, use **Use as** to override an ID to Numeric, a numeric code to
  Categorical, or a nearly unique string to Text. **Auto** restores inference;
  undo/redo and saved workspaces retain the choices.
- In **Relationships**, choose **Chart type**: Scatter, Count bars, Grouped
  count bars, Mean bars, Median bars or Sum bars. Only applicable columns appear.
  Bars include named missing categories and Other; click a bar to select its
  source rows. Expand, Height and numeric axis controls apply to the charts.
- In **Correlations**, choose **Pair grid**, then **Diagonal**: Histogram, KDE,
  ECDF, Box or Violin. Heatmap remains numeric Pearson correlation; categorical
  values are never silently converted to arbitrary numeric codes.

This completes this requested follow-up. The broader original Titanic UX gates
in `ux-implementation.md` remain independent; this does not mark them accepted.
