# Phase 3 verification evidence

## M3.1 Ordered operations and undo/redo

Entry: Phase 2 passed at `4480aad`. The clean worktree was inspected before
implementation. `eb62f92` introduces immutable operations and transactional
history; `49a3051` adds background editing, prepared previews, and GUI controls.

Sorting is stable with configurable direction and null placement. Filters
support comparisons and explicit null predicates; null comparison results are
excluded. Column selection keeps the specified order and requires at least
one distinct, existing column. Source IDs travel separately from user columns,
including regex-like names and internal-name collisions. History retains
recipes and source/current tables, rather than a full table snapshot per edit.
Undo replays from the source; redo applies the next recipe. Every publication
has a fresh revision. A successful branch drops redo history; failed edits do
not change the table, recipe, cursor, revision, or redo history.

Edits and summary/page preparation run in workers. Publication checks the
starting dataset revision. Abandoned or stale results cannot publish; executing
operations may still finish. Import requests abandon pending edits. Binding a
new imported dataset starts fresh history. Prepared preview pages are rebound
on every edit, preventing old pages from appearing after transformations.

```text
UV_CACHE_DIR=/tmp/datelier-uv-cache uv run --offline pyrefly check
                              0 errors
uv run pytest tests/test_pipeline.py tests/test_editing.py
                              8 passed
uv run pytest                 159 passed in 9.71s
uv run ruff check .           passed
uv run ruff format --check .  57 files formatted
git diff --check              passed
```

All uv commands use the temporary cache above because the host cache is
read-only inside the sandbox. Full tests also use `OMP_NUM_THREADS=1`,
`OPENBLAS_NUM_THREADS=1`, and `NUMBA_CACHE_DIR=/tmp/datelier-numba-cache`.

```sh
UV_CACHE_DIR=/tmp/datelier-uv-cache LIBGL_ALWAYS_SOFTWARE=1 POLARS_MAX_THREADS=8 \
  uv run --offline scripts/operations_smoke.py
```

The live Linux GUI rendered 68 frames and passed eight action/result checks,
including identity after sort/filter, prepared page invalidation, undo/redo,
failure preserving redo history, and a new branch discarding redo. Docked
panels and unchanged source bytes were verified. The screenshot was visually
inspected; human-readable history, active schema/null counts, and source IDs
are visible. [Report](evidence/operations-history.json) and
[screenshot](evidence/operations-history.png) retain the evidence. This check
invokes the same editor commands used by buttons from the frame hook; it does
not claim physical mouse input verification. Mesa software OpenGL is verified;
accelerated rendering remains unverified.

M3.1 passes. Final M3.2 and phase-exit evidence follows.

## M3.2 Mapping, derived columns and export

Entry: M3.1 passed and was recorded in `b2782b4` before M3.2 implementation.
`e00940a` adds typed transforms, `7f99783` derived expressions, and `1a9f991`
explicit export. `9a62fcd` fixes persistent input diagnostics and temporal
filters. `bc76f68` completes the nanosecond timestamp fix. The initial timestamp
patch at `d32b408` was committed while its regression still failed; it is not
passing evidence. The corrected code passed focused tests, Pyrefly/Ruff, and
GUI checks before the follow-up commit. `a411d22` adds acceptance coverage.

Casts target Int64, UInt64, Float64, Boolean, String, Date, or Datetime using
Polars conversions. Strict casts reject invalid conversions; disabling strict
mode permits invalid values to become null where the conversion supports it.
The active schema/null summary is recomputed and the selected policy appears
in history. Integer casts follow Polars semantics, including truncation of
fractional values; strict means conversion validity, not lossless conversion.
Missing-value operations fill or drop nulls, with an explicit option to include
NaN and infinity. Multi-column row dropping is supported by the recipe; the
GUI uses the selected column. Fill values convert to the existing dtype.

Lookup recipes store scalar pairs, output type, and an unmatched-key policy:
keep original, set null, or reject. Keys convert to the input dtype; duplicate
converted keys fail. Null keys are supported. Output conversion is strict,
including retained unmatched values. Invalid mappings preserve active state.
Filter null tests use explicit predicates; other comparisons exclude null
results. Dates/timestamps accept ISO values; comparisons retain nanoseconds.

Derived expressions compile an allowlisted AST to Polars without Python
execution. Supported syntax includes `col("literal name")`, scalar literals,
arithmetic `+ - * / // %`, chained comparisons, `and/or/not`, and the documented
numeric/string/null/conditional functions. Attribute access, indexing,
comprehensions, lambdas, arbitrary function calls, keyword arguments, and
unknown columns/functions fail. Bounds are 4,096 input characters, 256 syntax
nodes, 32 compilation levels, and 1,024 characters per text literal. Integer
literals are Int64-bounded; floating literals must be finite. Polars arithmetic
and null semantics apply; nonfinite results are retained, not silently dropped.
Column replacement requires an explicit setting. Operations retain row IDs.

Exports capture the selected dataset revision, run outside frame callbacks,
and publish a completed temporary file atomically. Existing destinations require
explicit replacement. Source paths, symlinks to sources, and hardlink aliases
are rejected even with replacement enabled. Failed writes preserve existing
files and clean temporary files. Exports contain user columns and no internal
IDs. Parquet preserves scalar schemas; CSV is textual and its reader may need
schema/date options to preserve numeric-looking strings or temporal types.
Closing the window lets an explicitly requested export finish. Export status
identifies the destination; its result retains the exported revision.

### Correctness and GUI evidence

The final 222-test suite includes:

- All six formats: import → sort → filter → fill → cast → map → derive → select
  → undo to source → redo → replay → CSV and Parquet export. Known values,
  column order, source IDs, revision-bound preview pages, and source bytes are
  asserted. CSV numeric-text columns use explicit reader schema overrides.
- Cast failures/null results, all-null and empty tables, duplicate/invalid
  mappings, unmatched strategies, null mapping keys, nonfinite handling,
  temporal comparisons, nanosecond timestamps, and literal column names.
- Expression success, rejection, complexity bounds, explicit replacement,
  empty/scalar results, and filesystem marker tests proving rejected code
  cannot execute. Failed edits and failed preview preparation retain the
  previous pipeline/inspection. Stale and abandoned work cannot publish.
- Atomic export failure and destination-race checks, source aliases, existing
  destinations, CSV quoting/Unicode/newlines/empty strings, zero-row exports,
  correct active-result round trips, and revision-bound background exports.

```sh
UV_CACHE_DIR=/tmp/datelier-uv-cache LIBGL_ALWAYS_SOFTWARE=1 POLARS_MAX_THREADS=8 \
  uv run --offline scripts/operations_smoke.py
# Repeat with scripts/transforms_smoke.py and scripts/export_smoke.py.
```

Final history checks pass eight actions in 68 frames. Initial typed-transform
checks pass six actions in 67 frames; final typed/expression checks pass eight
in 69 frames, including failure preservation and rejection of arbitrary Python.
Export checks pass CSV/Parquet round trips and source-replacement rejection in
66 frames. Reports and visually inspected screenshots:
[history](evidence/operations-history.json) / [image](evidence/operations-history.png),
[typed transforms](evidence/operations-transforms.json) / [image](evidence/operations-transforms.png),
[expressions](evidence/operations-expressions.json) / [image](evidence/operations-expressions.png),
[export](evidence/operations-export.json) / [image](evidence/operations-export.png).
The final XML import/settings/failure regression check also passed 90 frames.
These smoke checks exercise editor/exporter commands through the frame hook,
render their controls and results, and verify prepared state; they do not
claim physical button clicks. Mesa software OpenGL remains the verified renderer.

### Resource and responsiveness evidence

Use the Phase 0 reference budgets: ≤250 ms summaries, ≤50 ms page preparation,
≤33 ms GUI frame p95, and ≤1 GiB peak RSS for the specified synthetic fixtures.
No general transform-time or dataset-capacity guarantee is introduced.

```sh
UV_CACHE_DIR=/tmp/datelier-uv-cache POLARS_MAX_THREADS=8 \
  uv run --offline scripts/benchmark_operations.py
UV_CACHE_DIR=/tmp/datelier-uv-cache POLARS_MAX_THREADS=8 LIBGL_ALWAYS_SOFTWARE=1 \
  uv run --offline scripts/benchmark_operations.py --gui 1000000 6 \
  --output /tmp/datelier-operations-large.ppm
# Wide run: --gui 100000 64 --output /tmp/datelier-operations-wide.ppm
```

The [fresh-process report](evidence/operations-benchmark.json) contains one
measurement per shape, including hardware, versions, source sizes, width,
algorithm timings, and peak RSS. The fixture is Phase 0's deterministic table:
Int64 imported row_id, six (wide: 64) Float64 features, String category, and
nulls every 17 rows in the last feature. It sorts descending, filters to half
the rows, fills nulls, maps categories, derives a score, replays, undoes/redoes,
prepares summaries/pages, and round-trips both exports. Full row IDs are checked
against the user row_id values, and unchanged source metadata is asserted.
Temporary sources are freshly written, so reads use the local cache. Peak RSS
includes fixture generation, import, operations, replay, and export validation.

| Input shape | Replay ms | Undo + redo ms | Peak MiB |
| --- | ---: | ---: | ---: |
| 10k × 8 | 1.09 | 1.04 | 139.56 |
| 100k × 8 | 4.92 | 3.42 | 199.63 |
| 1m × 8 | 24.50 | 24.73 | 694.67 |
| 100k × 66 | 9.90 | 9.41 | 605.77 |

Summary and page maxima are 1.26 ms and 0.64 ms. Every component/memory budget
passes. These are single measurements, not repeated averages.

Live checks run the same five operations plus undo/redo through the background
editor, verify revision-bound pages after each command, navigate near the last
remaining row, and check its source identity. Wide runs display columns 49–64.
Both checks render only visible rows (maximum 29) and preserve source metadata.

| Input shape | Frames | Frame p95 ms | Peak MiB | Slowest edit to prepared ms |
| --- | ---: | ---: | ---: | ---: |
| 1m × 8 | 103 | 12.19 | 679.45 | 51.62 |
| 100k × 66 | 101 | 12.71 | 621.69 | 41.68 |

[Large report](evidence/operations-large.json) / [image](evidence/operations-large.png)
and [wide report](evidence/operations-wide.json) / [image](evidence/operations-wide.png)
retain the evidence. The screenshot review confirms descending source IDs,
transformed row counts, updated schemas, human-readable history, and prepared
wide/last-row pages. Edit timings include publication and preview preparation
observed on a later callback; they do not measure physical input latency.
Numeric benchmark behavior is unchanged by the subsequent temporal-only fix,
which passed its nanosecond regression and final full suite. The headless report
was rerun on that final code. Hardware/software match the earlier phases:
i7-13620H, 16 logical CPUs, 31.0 GiB RAM, Linux 7.0.0-34, Python 3.14.7,
Polars 1.44.2, ImGui Bundle 1.92.900, NumPy 2.5.3, eight Polars threads.

### Final phase checks

```text
uv run pyrefly check          0 errors
uv run pytest                 222 passed in 10.07s
uv run ruff check .           passed
uv run ruff format --check .  73 files formatted
uv lock --check --offline     passed; 24 packages
git diff --check              passed
```

Commands use the temporary uv cache and full-suite thread/cache settings
listed above. No dependencies changed. All M3.1 and M3.2 deliverables and exit
gates pass. Phase 3 is complete; Phase 4 automatic/interactive exploration is next.
