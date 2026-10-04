# Datelier

A simple personal Linux desktop tool for inspecting data, targeting Python 3.14+.
The verified v1 scope provides CSV/TSV, JSON/JSONL, Parquet, and tabular XML import,
responsive previews, schema/null summaries, reversible transformations,
explicit CSV/Parquet export, richer exploration with linked selections,
explicit PCA, t-SNE, UMAP and k-means analysis, referenced workspaces,
and saved layouts/themes/plot preferences.
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

Try a CSV with at least two varying numeric columns (for example `x` and `y`):

1. Open the file and inspect **Table preview**, **Schema and nulls** and **Explore**.
2. In **Transform and history**, sort `x`, then derive `score` with
   `col("x") * 2 + col("y")`. Try **Undo** and **Redo**.
3. In **Explore → Scatter**, choose `x` and `score`, then **Update raw scatter**.
   Click a row or point to see the matching highlight.
4. In **Analysis**, choose `x` and `y`, then **Run PCA**. Analysis is optional and
   always requires an explicit command; the other algorithms have sample settings.
5. In **Workspace**, enter a new `.datelier` path and **Save workspace**. Close
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

Enter a local dataset path and choose **Open dataset**. **Auto** detects the
format from its extension; use **Format** to override it. Expand **Import
options** for settings specific to that format. Imports run in the background;
failures retain the previous dataset.
**Abandon load** ignores the result while an executing parser may still finish.

Supported inputs and settings:

- **CSV/TSV:** strict UTF-8, delimiter, quoting, headers, null tokens,
  type/date inference, and skipped records. An empty delimiter uses the format
  default (comma or tab). Header-only files retain a zero-row schema.
- **JSON:** an array of flat record objects. **JSONL/NDJSON:** one flat record
  object per nonblank line. All records inform types and fields; missing fields
  become null. Choose text mode for mixed scalar types. Nested objects/arrays,
  duplicate keys, wrapped objects, and nonstandard nonfinite values fail with
  record/line/field context; flatten them into scalar columns first.
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

Open the **Workspace** tab next to Open dataset. Enter a destination path such
as `/path/to/session.datelier`, then choose **Save workspace**. Existing files
require **Replace existing workspace**. Save records the source reference and
fingerprint, import options, undo/redo history, analysis settings and views.
It does not bundle source data or fitted results. Sources must still match the
imported size/mtime when saving.

Use **Open workspace**, or launch directly:

```sh
uv run datelier --workspace /path/to/session.datelier
```

Restore checks the source and replays recipes in the background. Failures keep
the active data/history. If a source moved, enter **Replacement source** and
choose **Relink / retry source**. Content changes require **Accept changed source
content** before replaying against the new data. Relative sources may move
alongside their workspace. Available column views/settings restore; unavailable
plot columns reset. Restoring never launches ML; use an explicit Run command.
Selections and fitted results last for the session.

The **Preferences** menu offers Dark, Light and Classic themes, **Save
preferences**, **Restore saved layout**, **Reset layout** and **Reset plot
defaults**. Preferences also save on exit, including docking, panel visibility,
plot defaults and views. Use **View** to reopen closed panels. Layout reset
restores all panels without changing your dataset or history. Settings live in
`$XDG_CONFIG_HOME/datelier/preferences.json`, or
`~/.config/datelier/preferences.json` by default. Missing/outdated/invalid settings
recover with defaults and a status message. Global plot defaults apply on dataset
import; workspace settings take precedence when reopening. Zoom/pan and 3D
camera position last for the session. See [Phase 6 evidence](docs/phase-6.md).

## Exploration

The **Explore** panel automatically prepares numeric, categorical, and temporal
profiles after import and successful edits. Choose **Profiles**, **Scatter**, or
**Correlations**. Numeric profiles show finite ranges, means, and distributions;
quality counts identify null/nonfinite values. Temporal bins use units relative
to the minimum, with a precise range. Expand **Bin boundaries / category labels**
to read each bar's interval or category.

Automatic work profiles the first 32 columns, selects the first six numeric
columns, and suggests up to three scatter pairs. Correlations use at most 10,000
evenly spaced input rows with pairwise finite values. Scatter plots show up to
2,000 evenly spaced eligible points. Categorical counts use at most the first
100,000 input rows, show the top 12 values and Other, and truncate labels after
120 characters. Sampling and exclusions are labeled. Numeric plot coordinates
use Float64, so very large integers and high-precision decimals may round.

Expand **Plot settings** to change bins, top counts, profile limits and scatter
point limits. **Profile focus** can choose any column, including one beyond the
automatic limit. In **Profiles**, select a column and use **Chart type** to
switch directly between Histogram, KDE, ECDF, Box, and Violin for numeric
columns. Categories have named count bars; temporal histograms use formatted
date/time ticks. The included/missing summary stays visible, while **Details**
contains statistics and sampling settings. Single-column curves are prepared
on demand in the background; their chart type is saved with the workspace.

For multi-column comparisons, select up to eight columns under **Numeric
comparisons**, apply settings, and choose the comparison chart type in Profiles.
Histogram/KDE/ECDF curves overlay with selectable legends; boxes/violins appear
beside one another. Histograms share bins and default to density. Original units
are the default; optional z-scores use each column's full finite mean/deviation.
KDE uses Gaussian kernels with Scott bandwidth and a visible multiplier.
KDE/ECDF/violin use at most 2,000 finite values per column, sampled by source ID
and seed (default 42). Box quartiles/Tukey whiskers are exact; displayed outliers
use that sample, capped at 150. Empty/constant inputs have explicit explanations.
Categorical and temporal profiles remain available under Individual profiles.

In Scatter, **Coordinates → Columns** shows X/Y selectors; **Dimensions → 3D**
adds Z. Choosing PCA, t-SNE, or UMAP replaces the manual axes with that method's
inputs and Run command. **Color** selects another column: continuous
numeric/temporal colors, top-12 categorical colors plus Other, and neutral missing
values. Selected points retain their highlight. Column axes and colors update
in the background when changed. Analysis runs only after an explicit command.

In Correlations, **Features** chooses an ordered numeric list; **Apply features**
updates the view. **Chart type** switches between a Pearson heatmap (up to 16 features)
and a pair grid (default six, maximum eight). The grid option appears only for
eight or fewer features. Heatmap colors span
−1 to +1; gray cells are undefined and hover shows finite-pair counts. Click a
pair to open raw scatter. Grid diagonals show distributions; mirrored scatter
cells reuse up to 150 points from the common correlation cohort. Double-click a
scatter cell to open its axes; click a diagonal to open that column's profile.

**Apply plot settings** prepares a new dashboard in the background. Bounds are
128 leading profile columns, 100 bins/counts, 16 correlation features (120 pairs),
and 10,000 displayed scatter points in 2D or 3D. **Abandon exploration** ignores
its result while an executing preparation job may still finish.

Click a source row in the table or a plotted point to select it; Ctrl-click
toggles membership. A plot click brings its row into the table view. Shift-drag
brushes the displayed scatter points. Table rows and matching plot points share
highlights; selected rows outside the plot sample remain selected. Selections
are limited to 10,000 rows and clear when the dataset revision changes. Use the
wheel to zoom, middle-drag to pan, and **Fit scatter** or double-click to fit.
In 3D, left-drag rotates, right-drag pans, and the wheel zooms. Click picking and
Shift brushing use projected displayed points; camera gestures are disabled
during brushing. **Fit scatter** resets the bounds.
See [Phase 4 evidence](docs/phase-4.md) and
[richer-inspection evidence](docs/richer-inspection.md) for measured limits.

## On-demand analysis

In Scatter, choose PCA, t-SNE, or UMAP under **Coordinates**, then select
features under **Inputs and settings**. Choose preprocessing, dimensions,
seed and the algorithm's sample limit, then explicitly press its **Run** button.
The **Analysis** panel also provides these controls and **Run K-means**.
Defaults drop missing/nonfinite rows and standardize features; optional median
imputation and no scaling are available. Constant features are removed and
reported; unusable data or invalid parameter combinations fail without adjusting
your settings. Analysis uses source-ID/seed sampling before bounded NumPy conversion.

| Algorithm | Default sample / maximum | Initial settings |
| --- | ---: | --- |
| PCA | 10,000 / 100,000 | 2 components, randomized solver, no whitening |
| t-SNE | 2,000 / 10,000 | 2 components, perplexity 30, 1,000 iterations, PCA initialization, automatic learning rate |
| UMAP | 5,000 / 50,000 | 2 components, 15 neighbors, minimum distance 0.1, Euclidean metric |
| K-means | 10,000 / 100,000 | 3 clusters, 10 initializations, 300 iterations |

Settings are visible and seed defaults to 42. Embeddings support two or three
components; viewing a third component requires an explicit three-component run.
One spawned analysis worker runs at a time. The panel shows preparation/fitting
phases and elapsed time; **Cancel analysis** reports completion after the worker
exits. Dataset revisions invalidate results and stale jobs cannot publish.
These sample limits are bounds, not capacity guarantees.

Choose Columns or an embedding in Scatter to switch views without fitting
again. An unfitted method shows its setup; it never falls back to column axes.
Changed settings require another command. **Color → K-means clusters** uses the
completed clustering result on raw or reduced plots. Fitting samples and
nearest-center predictions in the original fitted feature space are disclosed;
excluded rows receive neutral colors. Provenance records inputs, exclusions,
sampling, preprocessing, parameters, seed, runtime and library versions.
Loading data, changing settings and editing never launch ML automatically.
K-means is the only current clustering algorithm; spectral, agglomerative,
DBSCAN and HDBSCAN remain future additions.
See [Phase 5 evidence](docs/phase-5.md) for correctness and resource measurements.

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
