# Phase 4 verification evidence

## M4.1 Type-aware profiles and automatic plots

Entry: Phase 3 passed. The worktree and current implementation were inspected.
`345a45e` adds bounded type-aware profiles; `4b144cb` adds plot preparation and
background lifecycle; `8bc4d29` renders the automatic dashboard. Each step
passed its focused tests, batch Pyrefly, Ruff lint/format, and diff checks
before its commit. The UI step also passed a live Linux smoke check.

Numeric profiles report null/nonfinite counts, finite range/mean, and exact
Polars histograms. Temporal profiles report their precise range and physical-unit
histograms relative to the minimum. Categorical profiles report deterministic top counts, distinct
counted values, and Other. Counts examine at most the first 100,000 rows and
label sampling; labels truncate to 120 characters. Nulls are excluded from
counts. Empty, all-null, constant, unsupported, and nonfinite inputs have
explicit outcomes. User names including `count` and regex-like names work.

Automatic work profiles the first 32 columns. Pearson correlations examine
at most eight numeric columns (28 pairs) and 10,000 evenly spaced input rows,
excluding invalid pairs. Constant/insufficient/overflow pairs are undefined.
Up to three pairs ranked by absolute defined correlation become scatter
suggestions. Each scatter examines the full chosen pair for eligibility and
shows at most 2,000 evenly spaced eligible points with stable source IDs.
Only selected, bounded coordinates cross the NumPy plotting boundary.
Sampling, eligibility counts, column bounds, and bin labels are visible.

Imports and successful edits automatically schedule exploration outside GUI
callbacks. The table preview becomes usable independently of exploration.
Obsolete requests are cancelled if queued or safely abandoned if executing;
revision checks prevent stale publication. Errors stay in the dashboard.
Loading a table runs no machine learning.

```text
UV_CACHE_DIR=/tmp/datelier-uv-cache uv run --offline pyrefly check
                                            0 errors
uv run --offline pytest tests/test_profiling.py tests/test_exploration.py
                                            8 passed
uv run --offline pytest                     230 passed in 9.85s
uv run --offline ruff check .                passed
uv run --offline ruff format --check .       80 files formatted
git diff --check                            passed
```

All uv checks use the temporary cache shown above. Full tests also set
`OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 NUMBA_CACHE_DIR=/tmp/datelier-numba-cache`.

```sh
UV_CACHE_DIR=/tmp/datelier-uv-cache LIBGL_ALWAYS_SOFTWARE=1 POLARS_MAX_THREADS=8 \
  uv run --offline scripts/exploration_smoke.py
```

The live GUI passed 83 frames: known numeric/category summaries, temporal
profile range, all three dashboard tabs, automatic scatter, and sorted
source-ID/plot revision refresh. Source bytes stayed unchanged. The
[report](evidence/exploration-dashboard.json) and visually inspected
[screenshot](evidence/exploration-dashboard.png) retain evidence. The smoke
uses frame-hook commands and tab state; physical input is not claimed here.
The verified renderer is Mesa software OpenGL. The sandbox cannot access X11,
so live checks run with local-display access. Accelerated rendering remains
unverified.

M4.1 passed before M4.2 work began at `e78ce06`. Final phase evidence follows.

## M4.2 Plot controls and linked selection

`8f9df0a` adds configurable profiles/scatters, zoom/pan controls, and linked
source-row selections. `7cfb81f` bounds selected-point rendering, fixes extreme
numeric and nanosecond temporal profiles, and adds all-format/resource gates.
Both steps passed Pyrefly, relevant behavioral tests, Ruff, diff checks, and
live GUI checks before committing. The final step passed the full suite and
resource gates as well.

Settings allow 1–128 leading profiles, 1–100 histogram bins/top counts, 2–16
numeric correlation columns (at most 120 pairs), and 1–10,000 scatter points.
A focused profile can select any column, including columns beyond 128; a
custom scatter can select any two numeric columns. Applying settings schedules
background preparation with visible status. Invalid settings/pairs have
explicit errors. Dropping chosen columns repairs the control choices before
repreparing. Defaults remain bounded. Numeric plotting uses Float64; very
large integers/decimals can round. Temporal binning shifts in integer space
before Float64 conversion, preserving close nanosecond differences. Temporal
ranges format in Polars so Python datetime conversion cannot lose precision.
Extreme finite ranges use explicitly labeled scaled histogram values; stable
means/correlations avoid sum/range overflow. Histogram counts must account for
all included values, preventing a silently empty chart.

Selections share source IDs rather than row positions. Scatter coordinates
carry their current display position too, allowing a click to reveal the
correct table row after sorting/filtering/sampling. Table clicks replace the
selection; Ctrl-click toggles it. Clicks match within eight screen pixels.
Shift-drag brushes displayed points only, with a visible rectangle. Table rows
and matching scatter points highlight together; unsampled table selections
remain selected. Selections cap at 10,000 and clear on revision changes; stale
plots cannot select against a newer revision. Wheel zoom, middle-button pan,
double-click fit, explicit Fit, and Clear controls work. Cached point partitions
draw selected/unselected data separately, without duplicating the whole plot.

### Correctness and GUI evidence

The final suite has 242 passing tests, including 20 exploration/selection tests:

- Known numeric/temporal distributions and categorical counts; null/nonfinite,
  empty, all-null, constant, unsupported, literal-name, and high-cardinality
  inputs. Extreme finite means/correlations/histograms and nanosecond
  Datetime/Duration/Time ranges and distributions have regression coverage.
- Default/wide pair and column caps, focused profiles beyond column 128, custom
  pairs beyond the correlation cap, point limits, invalid columns/settings,
  removed-column controls, immutable coordinate arrays, and source/display
  identity after sorting, filtering, and deterministic sampling.
- Table-to-plot and plot-to-table selection, brush membership, unsampled rows,
  toggles, stale selections, revision reset, selection limits, invalid geometry,
  background failures, new requests overtaking an old worker, safe abandonment,
  and stale-result rejection.
- All six formats: import → automatic exploration → sort/filter → sampled
  scatter/linked selection → undo, checking known summaries, exact IDs and
  positions, stale selection rejection, fresh revisions, and unchanged source
  bytes. No exploration path calls the analysis/ML modules.

```sh
UV_CACHE_DIR=/tmp/datelier-uv-cache LIBGL_ALWAYS_SOFTWARE=1 POLARS_MAX_THREADS=8 \
  uv run --offline scripts/selection_smoke.py
UV_CACHE_DIR=/tmp/datelier-uv-cache LIBGL_ALWAYS_SOFTWARE=1 POLARS_MAX_THREADS=8 \
  uv run --offline scripts/exploration_smoke.py --settings \
  --output /tmp/datelier-plot-settings.ppm
```

The selection run passed 169 live frames after sort/filter and four-point
sampling: plot click highlighted/revealed source row 10, a table click selected
it in the plot, wheel zoom reduced axis range, middle-drag changed bounds, and
Shift-drag brushed the correct ID. It uses Dear ImGui mouse/key events and the
backend cursor-position API; physical human input is not claimed. The settings
run passed 93 frames, showing the editable settings panel and precise temporal
schema while rechecking known profiles, correlations, scatter, edit invalidation,
and source preservation. Reports and visually inspected screenshots:
[selection](evidence/exploration-selection.json) /
[image](evidence/exploration-selection.png),
[settings](evidence/exploration-settings.json) /
[image](evidence/exploration-settings.png).

### Resource and responsiveness evidence

Before measurements, the exploration preparation budgets were declared as
≤2 seconds for default settings and ≤4 seconds for expanded settings on the
reference fixtures. Retained Phase 0 budgets are ≤250 ms baseline summaries,
≤50 ms preview page preparation, ≤33 ms frame/interaction p95, and ≤1 GiB peak
RSS. These are acceptance bounds for the specified fixtures, not universal
capacity or timing guarantees.

```sh
UV_CACHE_DIR=/tmp/datelier-uv-cache POLARS_MAX_THREADS=8 \
  uv run --offline scripts/benchmark_exploration.py
UV_CACHE_DIR=/tmp/datelier-uv-cache POLARS_MAX_THREADS=8 LIBGL_ALWAYS_SOFTWARE=1 \
  uv run --offline scripts/benchmark_exploration.py --gui 1000000 6 \
  --output /tmp/datelier-exploration-large.ppm
# Wide: --gui 100000 64 --output /tmp/datelier-exploration-wide.ppm
```

Four [fresh-process measurements](evidence/exploration-benchmark.json) use the
Phase 0 deterministic fixture: imported Int64 row_id, six (wide: 64) Float64
features, String category, and nulls every 17 rows in the final feature. Default
profiles/dashboard examine the full input. Expanded preparation follows
sort-descending/filter-to-half, using 128 profile columns, 100 bins/top counts,
16 correlation columns, and 10,000 scatter points. The chosen pair uses the
nullable final feature. Each of 50 interaction repetitions selects a point,
brushes the full displayed sample, and updates its cached overlay. Full sampled
source IDs are compared with the active table's row_id at prepared positions.
Source metadata stays unchanged. Temporary sources are freshly written, so
reads use the local cache. Peak RSS includes fixture generation, import,
source/current pipeline tables, profiles, coordinates, and selections.

| Input shape | Default preparation ms | Expanded preparation ms | Interaction p95 ms | Peak MiB |
| --- | ---: | ---: | ---: | ---: |
| 10k × 8 | 12.97 | 5.45 | 0.63 | 128.38 |
| 100k × 8 | 17.56 | 7.52 | 1.36 | 170.16 |
| 1m × 8 | 68.39 | 35.61 | 2.39 | 509.10 |
| 100k × 66 | 28.46 | 43.88 | 2.19 | 451.41 |

Baseline summary/page maxima are 1.27/0.97 ms. All resource budgets pass.
These are one fresh-process measurement per shape, not repeated averages;
interaction p95 uses 50 repetitions within that process.

The initial live large run failed the frame budget (41.43 ms p95) while drawing
10,000 selected points over the same 10,000 base points. Cached disjoint
partitions and square markers reduced rendering work while retaining all
10,000 displayed points and selection behavior. The final live gates run
imports/default preparation, expanded full-input settings, background sort
and filter with revision refresh, then render 10,000 selected points and
navigate the last remaining table rows. Wide runs display columns 49–64.
Both verify all sampled source IDs and highlighted visible rows; at most eight
table rows render in the default dock geometry.

| Input shape | Frames | First preview ms | Default preparation ms | Expanded preparation ms | Frame p95 ms | Peak MiB |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 1m × 8 | 140 | 160.92 | 110.22 | 111.29 | 17.51 | 679.21 |
| 100k × 66 | 131 | 145.82 | 55.21 | 119.06 | 17.73 | 622.70 |

[Large report](evidence/exploration-large.json) /
[image](evidence/exploration-large.png) and
[wide report](evidence/exploration-wide.json) /
[image](evidence/exploration-wide.png) retain evidence. Screenshot review
confirms updated schemas, sorted source IDs, visible sampling/eligibility,
selected points/table rows, and wide-column navigation. Preparation timings
measure publication observed by a frame callback and exclude import; first
preview includes import. Frame p95 includes loading, preparation, edits, and
steady selected-point rendering after warm-up. Hardware/software remain the
Phase 0 reference: i7-13620H, 16 logical CPUs, 31.0 GiB RAM, Linux 7.0.0-34,
Python 3.14.7, Polars 1.44.2, ImGui Bundle 1.92.900, NumPy 2.5.3, eight Polars
threads, Mesa software OpenGL. Accelerated rendering remains unverified.

### Completion audit and final checks

| Phase requirement | Authoritative evidence |
| --- | --- |
| Numeric/categorical/temporal profiles, distributions and counts | `profiling.py`, known/edge/precision tests in `test_profiling.py`, live dashboard smoke |
| Correlations and bounded suggestions | `plotting.py` / `exploration.py`, known/constant/overflow/wide tests, benchmark pair/point assertions |
| Automatic dashboard and revision-aware data | import/edit scheduling in `gui.py`, Explorer stale/failure/abandonment tests, live edit refresh |
| Unsuitable columns and excessive pairwise work | explicit profile/correlation diagnostics, type/settings tests, 28/120 pair caps |
| Column/plot controls and bounded expansion | `gui_plot_controls.py`, focus/custom/removed-column tests, settings screenshot, expanded benchmark settings |
| Zoom/pan and linked selection after sort/filter/sample | `selection.py` / GUI input handlers, identity/selection tests, live input-event gate |
| Visible sampling/truncation | profile notes/counts, scatter eligibility labels, settings and large/wide screenshots |
| Wide-table/resource/interaction limits | four fresh-process measurements and two live large/wide reports above |
| Source preservation and stale-result safety | all-format workflow bytes, worker lifecycle tests, source metadata/identity benchmark assertions |
| Full checks and verified step commits | commands below; `345a45e`, `4b144cb`, `8bc4d29`, `e78ce06`, `8f9df0a`, `7cfb81f` |

```text
uv run --offline pyrefly check          0 errors
uv run --offline pytest                 242 passed in 11.07s
uv run --offline ruff check .           passed
uv run --offline ruff format --check .  88 files formatted
uv lock --check --offline               passed; 24 packages
git diff --check                        passed
```

Commands use the temporary uv cache and full-suite thread/cache settings noted
in M4.1. No dependencies changed. Every M4.1/M4.2 deliverable and exit gate
passes. Phase 4 is complete; Phase 5 on-demand analysis is next.
