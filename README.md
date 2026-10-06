# Datelier

A simple personal Linux desktop tool for inspecting data, targeting Python 3.14+.
The verified v1 scope provides CSV/TSV, JSON/JSONL, Parquet, and tabular XML import,
responsive previews, schema/null summaries, reversible transformations,
explicit CSV/Parquet export, richer exploration with linked selections,
26 explicit clustering/embedding methods, referenced workspaces,
and saved layouts/themes/plot preferences. The completed Phase 9 adds independent
editor tabs, whole-session workspaces and cross-file profile comparisons.
Phase 10 adds reference interpretations, lazy image/text previews, conditional
table styles and gallery/detail Inspect for tables and media/text records.
Phase 11 is underway: structured JSON/TOML trees and named table views pass
M11.1; lazy arrays, record mappings and checkpoint inspection remain open.
See [ROADMAP.md](ROADMAP.md) for delivery gates and [AGENTS.md](AGENTS.md) for
contributor conventions.

## Personal setup

Use a Linux graphical session with OpenGL and Python 3.14+. Install
[uv](https://docs.astral.sh/uv/), then run from this checkout:

```sh
uv sync --locked --no-dev
uv run --no-dev datelier /path/to/data.csv
```

The tested environment is Linux x86_64, Python 3.14.7 and Mesa software OpenGL.
If the default renderer stalls, use
`LIBGL_ALWAYS_SOFTWARE=1 uv run --no-dev datelier /path/to/data.csv`.
Tables must fit in memory; sampling bounds plots/analysis, not source loading.
See [Phase 7 evidence](docs/phase-7.md) for the measured fixtures and limitations.

For a separate local install, build a wheel and install the locked runtime first:

```sh
uv build
UV_PROJECT_ENVIRONMENT=/tmp/datelier-install uv sync --locked --no-dev --no-install-project
uv pip install --python /tmp/datelier-install/bin/python --no-deps dist/datelier-0.1.0-py3-none-any.whl
uv pip check --python /tmp/datelier-install/bin/python
/tmp/datelier-install/bin/datelier /path/to/data.csv
```

Choose your own environment directory if you want to keep this installation;
`/tmp` is just an example. The source archive is also in `dist/`. Package version
0.1.0 identifies this personal-use build. Public publishing is not needed.

## First session

Try a CSV with an `id` column followed by at least two varying numeric columns
(for example `x` and `y`):

1. Open the file and inspect **Table preview**, **Schema and nulls** and **Explore**.
2. In **Transform and history**, sort `x`, then derive `score` with
   `col("x") * 2 + col("y")`. Try **Undo** and **Redo**.
3. In **Explore → Scatter**, choose `x` and `score`, then **Update raw scatter**.
   Click a row or point to see the matching highlight.
4. In **Analysis**, choose `x` and `y`, then **Run PCA**. Analysis is optional and
   always requires an explicit command; the other algorithms have sample settings.
5. Choose **File → Workspace actions…**, enter a new `.datelier` path and
   **Save workspace**. Close
   and reopen with `datelier --workspace /path/to/session.datelier` (prefix with
   `uv run --no-dev` when using the checkout).
6. Check the restored table/history/settings. Fitted analysis results are
   session-only; rerun explicitly if needed. Keep the source file available,
   or use the workspace's relink controls if it moved.
7. In **Export table**, choose a new destination and CSV or Parquet, then
   **Export active table**. The source file stays unchanged.

## Development

Install [uv](https://docs.astral.sh/uv/), then run:

```sh
uv sync --locked
uv run datelier
uv run pyrefly check
uv run pytest
uv run ruff check .
uv run ruff format --check .
```

`uv sync` installs the default `dev` group with Pyrefly, pytest, and Ruff.
Use `uv sync --no-dev` for runtime dependencies alone.

## Data workbench

On a Linux graphical session:

```sh
uv run datelier
uv run datelier /path/to/data.csv
```

Welcome offers **Open Files**, **Open Folder**, a path/retry action and recent
files/workspaces. Multiple selected files open independent tabs; reopening a
source focuses its tab. Tabs switch, reorder and close, and **New Tab** opens
Welcome. Choose **File → Import settings…** for contextual format/options.
**Auto** detects the format from its extension; use **Format** to override it.
**Reimport source (resets history)** applies changed options to that tab.
Imports run in the background; failed reimports retain the previous dataset.
**Abandon load** ignores the result while an executing parser may still finish.

Supported inputs and settings:

- **CSV/TSV:** strict UTF-8, delimiter, quoting, headers, null tokens,
  type/date inference, and skipped records. An empty delimiter uses the format
  default (comma or tab). Header-only files retain a zero-row schema.
- **JSON:** an array of flat record objects. **JSONL/NDJSON:** one flat record
  object per nonblank line. All records inform types and fields; missing fields
  become null. Choose text mode for mixed scalar types. Explicit flat imports
  reject nested fields with record/line/field context. Invalid syntax, duplicate
  keys and nonstandard JSON nonfinite values remain errors.
- **Structured JSON/TOML:** `.toml` opens its preserved hierarchy; JSON that
  cannot form a flat table opens the Source browser. Choose **JSON / TOML object**
  in import settings or **Browse JSON source** to browse a flat JSON source.
  Expand nodes, select a record array, then **Open records as table view**.
  The **Record view** selector switches between Source and named tables with
  independent transformations and selections. Nested record fields require
  selecting another compatible node; mixed scalar fields can use text mode.
  Whole-session workspaces save node/view recipes and retain the original tree.
- **Parquet** (`.parquet`/`.pq`): preserves stored scalar types. Optionally choose
  columns by name, separated by `|`; empty means all columns. Exclude nested
  columns or flatten them before importing. Zero-row schemas are supported.
- **XML:** UTF-8 tabular records. The default `./*` selects root children.
  Use `./records/record`, `.//record`, or `.` for a single root record. Paths
  support element names, wildcards, and a leading descendant search; XPath
  predicates are unsupported. For namespaces, enter `prefix=URI` aliases
  separated by `|` and use `./prefix:record`, or use `{URI}record` names directly.
  Qualified names remain distinct in the table. Attributes become `@name`
  and `field/@name` columns; excluding them is explicit and reported.
  Configure whitespace trimming, text/type inference, ISO dates, and null
  tokens. Missing/empty fields become null. Nested/repeated fields, mixed
  content, and DTD/entity declarations fail with actionable diagnostics.
- **Media / text:** individual images, audio or UTF-8 text files open as metadata
  records, with lazy image thumbnails/text excerpts. In **Open Folder**, choose
  **Open folder as media collection**; **Include media subfolders** controls
  recursive membership. **Text: one record per line** explicitly reads text
  into line records, retaining empty lines and original line numbers.

Validated JSON/XML imports run in bounded record batches before producing the
in-memory Polars table. On the reference machine, the 1m × 8 fixtures took
about 8–12 seconds headlessly and 14–23 seconds in the live GUI for
JSON/JSONL/XML; TSV and Parquet were substantially faster.
Rendering remains responsive during these jobs. These are measured fixtures,
not a general capacity guarantee. See [Phase 2 evidence](docs/phase-2.md).

Scroll the table or use **Go to row**. Navigate wide tables with the column
buttons; every column remains accessible. Previews render visible rows, load
bounded pages, and truncate cells after 256 characters. The schema panel shows
inferred types and full-column null counts. Drag the tabs to rearrange panels.
Source files are read without modification. Loading does not run ML.

Use `LIBGL_ALWAYS_SOFTWARE=1 uv run datelier` on the reference machine if the
default renderer stalls; accelerated rendering remains unverified. See
[Phase 1 evidence](docs/phase-1.md) for verification and performance limits.
Referenced workspace recipes are available; fitted results remain session-only.

## Workspaces

Choose **File → Workspace actions…**. Enter a destination path such
as `/path/to/session.datelier`, then choose **Save workspace**. Existing files
require **Replace existing workspace**. Save records all tabs and their order,
the active tab, independent source references/fingerprints, import options,
undo/redo histories, analysis settings, views and selections (up to 10,000 row
IDs per file), plus docking and panel visibility. It does not bundle source data
or fitted results. Sources must still match the imported size/mtime when saving.

Use **Open workspace**, or launch directly:

```sh
uv run datelier --workspace /path/to/session.datelier
```

Restore checks sources and replays recipes in the background. A missing or
changed source gets its own recovery tab while other files remain usable. Enter
**Replacement source** there and choose **Relink / retry source**. Content changes
require **Accept changed source content** before replaying. Acceptance clears
changed tabular selections; fixed media manifests/line counts retain known source
IDs and missing-record placeholders. **Refresh media manifest on reload**, then
**Reimport source**, explicitly picks up current members/line counts. Relative
sources may move alongside their workspace.
Available column views/settings restore; unavailable plot columns reset with a
message. Legacy single-source workspaces open as one-file sessions. An invalid
workspace leaves the current editor intact. Restoring never launches ML; use an
explicit Run command. Fitted results last for the session.

The **Preferences** menu offers Dark, Light and Classic themes, **Save
preferences**, **Restore saved layout**, **Reset layout** and **Reset plot
defaults**. Preferences also save on exit, including docking, panel visibility,
plot defaults, views and recent sources. Older layouts with the removed import/
workspace panels reset while preserving other preferences. Use **View** to reopen
closed panels. Layout reset
restores all panels without changing your dataset or history. Settings live in
`$XDG_CONFIG_HOME/datelier/preferences.json`, or
`~/.config/datelier/preferences.json` by default. Missing/outdated/invalid settings
recover with defaults and a status message. Global plot defaults apply on dataset
import; workspace settings take precedence when reopening. Zoom/pan and 3D
camera position last for the session. See [Phase 6 evidence](docs/phase-6.md).

## Compare files

Open the training and test files, then choose **Compare files** (beside Explore,
or through **View**). Choose **New comparison**, expand **Mappings and scales**,
and check each file to map its column explicitly. Column names can differ.
Set source labels/colors, shared bins or top categories, then **Update comparison**.
You can keep up to 32 comparisons, each mapping at most 32 files.

Numeric columns share histogram bins; categorical columns share an order based
on pooled counts, with the remaining categories combined as **Other**. **Count**
shows rows. **Density / proportion** gives each numeric distribution unit area,
or divides category counts by that file’s row count, so unequal file sizes are
comparable. Numeric null/nonfinite values are excluded and reported; category
counts retain them. Summaries appear beside the chart in a scrollable table.
Incompatible roles/types or unavailable columns show a diagnostic. Change a
column’s analysis role in **Schema and nulls** when needed.

Choose **Selection source**, then click a bin/category or use **Select matching
source rows**. Selection activates that file and selects up to its first 10,000
matching rows; the message reports the full match count. Other files keep their
selections. Edits refresh comparisons that use that file. Applied mappings,
labels, colors and scales save with the whole-session workspace; fitted results
are still excluded. See [Phase 9 evidence](docs/phase-9.md) for native checks and
fixture-specific resource measurements.

## Reference previews and Inspect

**Schema and nulls → Interpretation** explains inferred roles and allows reversible
overrides. Recognizable image/audio/text references and prose take precedence over
identifiers. Otherwise, a nonempty, unique, non-null integer/string first source
column becomes Identifier; floating columns do not qualify through uniqueness.
Change the role when that first column is an ordinary measurement or category.
The physical dtype and original cell value stay visible.

In **Table preview → Reference previews**, configure search roots, extensions,
thumbnail size and CPU/GPU retention limits. Discovery runs in the background;
exact absolute/dataset-relative paths resolve first, then unambiguous filenames
or stems. **Choose reference** handles ambiguous or missing matches by selecting
a candidate or entering **Exact file**. Hover for text excerpts and diagnostics.
Direct media sources resolve their own paths without automatic nearby discovery.

**Cell presentation** offers blue-to-red numeric shading with percentile (2–98),
linear min/max or custom scales, stable category colors and interpretation badges.
`<`/`>` mark values outside the scale, `=` a flat scale, `(null)` typed nulls and
`!` nonfinite values. Selected rows use their selection color.

Open **Inspect** through **View**, or open a media collection to focus it. Choose
Gallery or focused Previous/Next navigation. **Inspect settings** selects current
row ranges, linked selection or reproducible seeded samples and a primary field.
**Supporting fields** can include every column, with search, All/Clear and Done.
Select a source-row label to link its table position. Sorting retains sampled
source identity, and each file keeps its own selection and Inspect settings.

Workspaces preserve these controls, reference mappings and record manifests;
decoded previews remain session caches. Missing records restore with diagnostics.
Exports and workspace writes preserve collection members as well as individual
source files. Full text statistics/tokenization, image tools and audio playback
arrive in the later authorized phases. See [Phase 10 evidence](docs/phase-10.md)
for native checks, restoration and fixture-specific resource measurements.

## Exploration

The **Explore** panel automatically prepares numeric, categorical, and temporal
profiles after import and successful edits. Choose **Profiles**, **Relationships**,
or **Correlations**. Schema shows `Shape: (rows, cols)` above **Column**, **Non
nulls**, **Uniques**, **Type**, and **Interpretation**. Non-null and unique counts
exclude nulls; NaNs and infinities remain non-null values. Interpretation allows
reversible overrides of inferred column roles.

Automatic work profiles the first 32 columns, selects the first six numeric
columns, and suggests up to three scatter pairs. Correlations use at most 10,000
evenly spaced input rows with pairwise finite values. Scatter plots show up to
2,000 evenly spaced eligible points. Categorical counts use at most the first
100,000 input rows, show the top 12 values and Other, and truncate labels after
120 characters. Sampling and exclusions are labeled. Numeric plot coordinates
use Float64, so very large integers and high-precision decimals may round.

Expand **Plot settings** to change bins, top counts and scatter point limits.
In **Profiles**, the **Columns** checklist accepts one category/date or any
number of numeric columns, including columns beyond the automatic preparation
limit. **All numeric**, **Clear**, and **Done** manage the checklist. Selecting a
category replaces the numeric group; selecting a numeric column replaces the
category. **Chart type** switches between Histogram, KDE, ECDF, Box, and Violin.
Categories have named count bars; temporal histograms use formatted date/time
ticks. The selection and chart type are saved with workspaces and preferences.

The **Statistics** table below the plot has one row per column, with names frozen
while scrolling. Numeric rows show mean, sample std (ddof=1), min, 25%/50%/75%,
max, non-null/unique/null counts, NaNs, total non-finite counts, mode and its
frequency. Moments and quantiles exclude non-finite values; floats round to two
decimal places for mode, and the smallest tied mode is shown. Undefined or
unrepresentable statistics display a dash. Statistics always use original units.
Categories show counts and mode; dates show ranges. Sampled counts/modes are
labeled. All computation runs in background workers.

Numeric Histogram/KDE/ECDF curves overlay with selectable legends and matching
statistics-row colors; boxes/violins appear beside one another. Histograms share
bins and default to density. **Distribution settings** offers histogram density,
z-score plots, bandwidth, and seed. Original units are the default; optional
z-scores use each column's full finite mean/deviation.
KDE uses Gaussian kernels with Scott bandwidth and a visible multiplier.
KDE/ECDF/violin use at most 2,000 finite values per column, sampled by source ID
and seed (default 42). Box quartiles/Tukey whiskers are exact; displayed outliers
use that sample, capped at 150. Empty/constant inputs have explicit explanations.

In **Relationships**, **Chart type** offers Scatter 2D, Scatter 3D, Box, Violin,
and Grouped count bars when compatible columns exist. Box/Violin show **Category** and a
numeric **Value**; grouped bars show **Category** and a distinct categorical
**Group by**. Single-column count bars are in Profiles. Older saved count views
reopen there with their category and plot height; saved mean/median/sum bars
reopen as Box with the same columns.

Category distributions use up to the first 100,000 input rows, exclude missing
or nonfinite numeric values, and show the top 12 categories plus Other. Missing
categories keep a named group. Quartiles and Tukey whiskers use every retained
finite value; violin density and displayed outliers use seeded samples of up to
2,000 values per category, with at most 150 outliers displayed. **Distribution
settings** controls bandwidth and seed. Extreme numeric coordinates use labeled
scaling. Click a box/violin to select that category's retained finite rows;
click a grouped bar to select its rows, capped at 10,000 with a visible message.

Scatter 2D and Scatter 3D have independent plot heights and native view state.
**Coordinates → Columns** places X/Y selectors beneath Coordinates, with Z in
Scatter 3D. Choosing a reduction fixes its component count at two or three to
match the selected plot and replaces the manual axes with that method's
inputs and Run command. **Colors** chooses Uniform, Column, or a clustering
method. Only Column shows the column picker: continuous numeric/temporal colors,
top-12 categorical colors plus Other, and neutral missing values. Clustering
shows its own settings and explicit Run button. Selected points retain their
highlight. Column axes and colors update
in the background when changed. Category and cluster colors use clickable native
plot legends in both dimensions, including Other, missing, noise and unassigned
groups when present. Hiding a group also hides its selection highlight and
excludes it from picking/brushing; its source rows remain selected in the table.
Continuous colors have a labeled color bar beside the plot. Analysis runs only
after an explicit command.
A fitted reduction with a different component count requires a rerun for the
chosen plot.

In Correlations, **Features** chooses an ordered numeric list; **Apply features**
updates the view. **Chart type** switches between a Pearson heatmap (up to 16 features)
and a pair grid (default six, maximum eight). The grid option appears only for
eight or fewer features. Heatmap cells show Pearson values to two decimal places,
with a matching **Pearson r** color bar from −1 to +1. Gray cells show a dash for
undefined correlations; hover shows finite-pair counts. Wide matrices scroll
horizontally to retain readable values and names, with the color bar alongside. Click a
pair to open raw scatter. Grid diagonals show distributions; mirrored scatter
cells reuse up to 150 points from the common correlation cohort. Double-click a
scatter cell to open its axes; click a diagonal to open that column's profile.
Dense grids show feature names across the top and down the left. Large grids
scroll inside the chart area, retaining space for full names and readable cells.

**Apply plot settings** prepares a new dashboard in the background. Bounds are
128 leading profile columns, 100 bins/counts, 16 correlation features (120 pairs),
and 10,000 displayed scatter points in 2D or 3D. **Abandon exploration** ignores
its result while an executing preparation job may still finish.

Click a source row in the table or a plotted point to select it; Ctrl-click
toggles membership. A plot click brings its row into the table view. Shift-drag
brushes the displayed scatter points. Table rows and matching plot points share
highlights; selected rows outside the plot sample remain selected. Selections
are limited to 10,000 rows and clear when the dataset revision changes. Use the
wheel to zoom, middle-drag to pan, and **Fit axes** or double-click to fit.
In 3D, right-drag rotates, left-drag pans, and the wheel zooms. Click picking and
Shift brushing use projected displayed points; camera gestures are disabled
during brushing. **View face** offers Top/Bottom (XY), Front/Back (XZ), Left/Right
(YZ), and Isometric. Choosing a face preserves zoom and selection and permits
further free rotation. **Fit axes** resets the bounds.
See [Phase 4 evidence](docs/phase-4.md) and
[richer-inspection evidence](docs/richer-inspection.md) for measured limits.

## On-demand analysis

In Relationships with Scatter selected, choose a method under **Coordinates**
or **Colors**, then select
features in its **inputs and settings**. Choose preprocessing, seed and sample
limit, then press **Run**. The Scatter 2D/3D chart determines coordinate output. Colors
methods hide output dimensions and use the original analysis feature space.
The **Analysis** panel follows the source you change or the setup you open.
Defaults drop missing/nonfinite rows and
standardize features; median imputation and original units are available.
Constants are removed and reported. Invalid inputs/settings fail clearly;
selection, import and workspace restore never launch analysis.

| Coordinate methods | Default rows / maximum |
| --- | ---: |
| PCA | 10,000 / 100,000 |
| t-SNE | 2,000 / 10,000 |
| UMAP | 5,000 / 50,000 |
| Truncated SVD | 10,000 / 100,000 |
| FastICA, Factor analysis, NMF | 10,000 / 50,000 |
| Kernel PCA | 2,000 / 3,000 |
| Gaussian / Sparse random projection | 10,000 / 100,000 |
| Isomap | 2,000 / 3,000 |
| MDS (metric or nonmetric) | 2,000 / 2,000 |
| Spectral embedding | 2,000 / 5,000 |
| Locally linear embedding (standard, modified, Hessian, LTSA) | 2,000 / 2,000 |

| Colors methods | Default rows / maximum |
| --- | ---: |
| K-means, Mini-batch K-means | 10,000 / 100,000 |
| DBSCAN | 2,000 / 5,000 |
| HDBSCAN | 2,000 / 10,000 |
| OPTICS | 2,000 / 5,000 |
| Gaussian / Bayesian Gaussian mixture | 10,000 / 50,000 |
| Agglomerative | 2,000 / 5,000 |
| Birch | 10,000 / 100,000 |
| Mean shift | 2,000 / 5,000 |
| Spectral clustering | 2,000 / 3,000 |
| Affinity propagation | 2,000 / 2,000 |

Settings show relevant alternatives: spectral affinity uses neighbors or gamma;
mean shift uses estimated or manual bandwidth; affinity propagation uses
automatic or manual preference. NMF explicitly exposes minmax input scaling to
[0, 1]; disabling it requires nonnegative inputs. LLE validates neighborhood
requirements for the chosen variant. Fit warnings and diagnostics are retained
in result provenance. See [method details and verification](docs/unsupervised-methods.md).

Settings are visible and seed defaults to 42. Embeddings support two or three
components; viewing a third component requires an explicit three-component run.
One spawned analysis worker runs at a time. The panel shows preparation/fitting
phases and elapsed time; **Cancel analysis** reports completion after the worker
exits. Dataset revisions invalidate results and stale jobs cannot publish.
These sample limits are bounds, not capacity guarantees.

Choose Columns or an embedding in Relationships to switch views without fitting
again when its component count matches the chosen scatter chart. An unfitted
method shows its setup; it never falls back to column axes.
Changed settings require another command. Colors uses the selected completed
clustering result on raw or reduced plots. K-means and Mini-batch K-means predict
displayed rows by nearest center; other methods color known fitting identities.
Noise has a distinct color/legend from unassigned or excluded rows. Fit samples
and any prediction are disclosed. Provenance records inputs, exclusions,
sampling, preprocessing, parameters, seed, runtime and library versions.

## Chart space and axes

Charts fill the available panel height. Drag the **Plot height** divider below
the chart, or drag/type its **Height** value above it, to choose a taller region.
**Auto** restores adaptive height. **Expand** opens the same chart in a larger
window; **Restore** returns it with its current zoom, selection, and 3D camera.
Manual chart heights are saved in workspaces and preferences.

For numeric 2D axes, **Axes** exposes minimum/maximum and Linear or Symmetric log
scales. Log 10 appears for a positive range. **Apply ranges** validates both axes
before changing the view, and subsequent wheel zoom and pan remain available.
**Fit axes** fits the displayed data. Category coordinates and formatted temporal
coordinates omit numeric editing; heatmaps keep their feature axes. Axis edits
are session state and reset when the plotted columns or chart type change.
Loading data, changing settings and editing never launch ML automatically.
See [Phase 5 evidence](docs/phase-5.md) for baseline correctness/resource
measurements and [unsupervised expansion](docs/unsupervised-methods.md) for the
new catalog and verification.

## Transform and export

Use the **Transform and history** tab to sort a named column, filter rows with
comparisons or null predicates, or keep columns in a specified order. Filter
values accept numbers, booleans, and text; quote numeric-looking text such as
`"1"`. Dates and timestamps accept ISO values. Column selection uses a JSON list,
for example `["name", "value"]`. Source row IDs stay aligned through edits.

Expand **Types, missing values and mappings** to cast a column, fill/drop missing
values, or apply a lookup. Invalid casts can fail or become null where supported;
integer casts use Polars truncation semantics. Null counts update after each
edit. **Treat nonfinite as missing** includes NaN and infinity. Lookup pairs use
`[["old", "new"], ["other", "next"]]` with an explicit output type and policy for
unmatched keys: keep, null, or reject.

Expand **Derived columns** to enter a column name and constrained expression,
for example `fill_null(col("price"), 0) * col("quantity")`. The panel documents
supported arithmetic, comparisons, conditional, numeric, text, and null
functions. Expressions cannot execute Python. Replacing an existing column
requires an explicit setting.

Edits run in the background. **Undo** and **Redo** restore replayed results;
a successful new edit after undo discards redo history. Failed edits retain the
active table and history. **Abandon edit** ignores an executing result; it may
still finish. Opening a new dataset starts new history. Source files stay
unchanged. Workspace files preserve the full history and undo/redo cursor.

Use **Export table**, choose CSV or Parquet and a destination, then select
**Export active table**. Replacing an existing destination requires its checkbox;
source files and their aliases are always protected. Exports contain user
columns in the active order. Parquet retains scalar schemas; CSV is text, so
reimport may need schema/date options for numeric-looking strings and dates.
A requested export finishes if the window closes. See
[Phase 3 evidence](docs/phase-3.md) for correctness and performance checks.

## Phase 0 GUI probe

On a Linux graphical session with OpenGL support:

```sh
uv run datelier --feasibility
uv run datelier --feasibility --smoke-frames 120
```

The verified renderer on the Phase 0 reference machine is Mesa software OpenGL:
use `LIBGL_ALWAYS_SOFTWARE=1 uv run datelier --feasibility` if the default
renderer stalls. Accelerated rendering remains unverified on that machine.

The probe shows a deterministic synthetic Polars table and a bounded scatter
plot in two dockable panels. Drag the tabs to rearrange them; zoom and pan in
the plot. This remains a stack integration probe alongside the data workbench.
Loading the probe does not run machine learning.

Run the tiny analysis compatibility probes explicitly:

```sh
OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 uv run scripts/analysis_smoke.py
```

See [Phase 0 evidence](docs/phase-0.md) for dependency versions, settings,
GUI observations, and performance measurements.

Reproduce the synthetic table benchmark (large CSVs are temporary):

```sh
POLARS_MAX_THREADS=8 uv run scripts/benchmark_feasibility.py
```

The JSON report is written to `/tmp/datelier-benchmark.json`. The plot probe
defaults to the first 2,000 finite rows and labels truncation explicitly.
