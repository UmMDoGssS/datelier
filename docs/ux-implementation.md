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
