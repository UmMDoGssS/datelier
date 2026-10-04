# Datelier

A Linux desktop data inspection workbench for analysts, targeting Python 3.14+.
Phase 3 provides CSV/TSV, JSON/JSONL, Parquet, and tabular XML import,
responsive previews, schema/null summaries, reversible transformations, and
explicit CSV/Parquet export.
See [ROADMAP.md](ROADMAP.md) for delivery gates and [AGENTS.md](AGENTS.md) for
contributor conventions.

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
Saved workspaces and automatic exploration follow in later phases.

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
unchanged. History is currently kept for the running session.

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
