# Phase 1 evidence

Recorded on 2026-10-04 on the Linux/Python 3.14.7 reference environment from
[Phase 0](phase-0.md). Commands use `UV_CACHE_DIR=/tmp/datelier-uv-cache`.

## M1.1 CSV import and dataset state

The headless dataset contract keeps UInt64 source-row IDs separate from user
columns. Reordering/filtering requires aligned IDs, validates uniqueness/range,
and publishes a distinct revision of the same dataset. Public Polars access
uses shallow clones to protect stored revisions without copying column buffers.
Independent imports receive independent dataset identities.

CSV import uses Polars with explicit delimiter, header, quote, null-token,
inference, date, and skipped-record options. UTF-8 is strict. Empty files fail;
header-only files retain a zero-row schema and display a diagnostic. Missing
trailing fields become null; extra fields and invalid quoting/UTF-8 fail.
Mixed columns infer as strings within the inference window; later conflicts
fail with advice to infer all rows or load text. Duplicate headers use Polars'
deterministic suffixes. Source metadata is checked before/after reading;
detected changes prevent publication. Metadata checks do not detect changes
that preserve size, modification time, and inode.

Tests include ordinary numeric/string values, user `row_id` collisions, quoted
delimiters/multiline values, Unicode, custom options, missing/null fields,
mixed inference, header-only/duplicate headers, malformed/empty/missing input,
external source changes, source-byte preservation, revision isolation, and
invalid row identity. The filename contains glob metacharacters to verify
literal file access.

```text
uv run pyrefly check          0 errors
uv run pytest tests/test_import_csv.py tests/test_dataset.py
                             22 passed
uv run pytest                39 passed in 9.32s
uv run ruff check .          passed
uv run ruff format --check .  21 files formatted
git diff --check             passed
```

The full suite used `OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1` and
`NUMBA_CACHE_DIR=/tmp/datelier-numba-cache`. After the two final lint fixes,
Pyrefly, all 22 focused tests, lint, format, and whitespace checks passed again.
M1.1 passes.

## M1.2 Responsive preview and job lifecycle

`uv run datelier [path.csv]` opens the workbench. Dockable import, table, and
schema/null panels show settings, loading, completion, failure, and abandonment.
Reads, full-column null counts, and page conversion run in workers. ML does
not run. Two import workers allow a new request to bypass one abandoned parser.
Queued obsolete requests are cancelled; executing results are ignored when
obsolete. Publication checks the request and active dataset revision. Failures
retain and identify the previous valid source. Abandonment does not claim the
parser stopped; Python may wait for executing workers at process termination.

ImGui's clipper renders visible rows. Pages hold at most 100 rows × 16 columns;
the revision-bound cache holds four pages and at most two pending requests.
Column buttons expose every column; the scrollbar and row control expose every
row. Cells label nulls, escape line breaks/tabs, and truncate at 256 characters.
An eight-pixel row grid retains aligned geometry at large float scroll offsets.
Page failures display an error and permit retry.

Headless tests verify blocked old parsers cannot replace newer data, revision
changes reject results, 20 obsolete queued requests never execute, abandoned
parser failures cannot publish, and failed loads preserve active data. Preview
tests verify bounds, aligned IDs, eviction/invalidation, and failure/retry.
Invalid CLI arguments fail before GUI startup.

### GUI acceptance checks

```sh
POLARS_MAX_THREADS=8 LIBGL_ALWAYS_SOFTWARE=1 uv run scripts/inspection_smoke.py \
  --rows 10000 --output /tmp/datelier-inspection-small.ppm
POLARS_MAX_THREADS=8 LIBGL_ALWAYS_SOFTWARE=1 uv run scripts/inspection_smoke.py \
  --rows 100000 --output /tmp/datelier-inspection-medium.ppm
POLARS_MAX_THREADS=8 LIBGL_ALWAYS_SOFTWARE=1 uv run scripts/inspection_smoke.py \
  --rows 1000000 --output /tmp/datelier-inspection-large.ppm
POLARS_MAX_THREADS=8 LIBGL_ALWAYS_SOFTWARE=1 uv run scripts/inspection_smoke.py \
  --rows 100000 --numeric-columns 64 --output /tmp/datelier-inspection-wide.ppm
POLARS_MAX_THREADS=8 LIBGL_ALWAYS_SOFTWARE=1 uv run scripts/inspection_smoke.py \
  --scenario switch-failure --output /tmp/datelier-inspection-switch.ppm
```

All runs rendered 180 frames with distinct table/schema dock IDs 2/4. Preview
cases reload the real CSV at frame 20 during rendering, jump near the last row
at frame 60, and inject actual ImGui mouse-wheel input at frame 100. Assertions
verify new revisions, prepared visible rows, source-row identity at the last
row, and wheel-induced scroll. At most 29 rows render per frame independently
of source size. The wide case exercises columns 49–64 of 66. Timing observation
conservatively detects displayed rows on the following callback; it is not a
hardware input-latency measurement.

| Rows × columns | Startup to visible ms | Live reload to visible ms | Frame p95 ms | Wheel to prepared ms | Peak RSS MiB |
| --- | ---: | ---: | ---: | ---: | ---: |
| 10k × 8 | 100.70 | 23.87 | 12.56 | 34.79 | 292.21 |
| 100k × 8 | 104.33 | 25.35 | 12.65 | 35.47 | 331.27 |
| 1m × 8 | 109.65 | 59.64 | 12.41 | 34.42 | 672.47 |
| 100k × 66 | 120.26 | 59.81 | 12.98 | 36.91 | 666.11 |

Maximum frame interval during observed reload: 18.46 ms (1m) and 18.62 ms
(wide). Last-row jump to prepared display: 32.68 and 33.90 ms. Applicable
Phase 0 loading, frame, and memory budgets pass. Input response is measured
explicitly; Phase 0 did not define a separate hardware input-latency budget.

The switch/failure case holds the first parser until a newer CSV loads, then
requests a missing file and releases the old parser. It renders 30 loading and
120 failed-state frames. Assertions confirm the newer dataset survives both
old completion and later failure. Its final screenshot shows the error, valid
active source, correct values, `NULL`, and schema/null counts. Frame p95: 9.03 ms.

Retained reports and visually inspected screenshots:

- [10k report](evidence/inspection-small.json), [screenshot](evidence/inspection-small.png)
- [100k report](evidence/inspection-medium.json), [screenshot](evidence/inspection-medium.png)
- [1m report](evidence/inspection-large.json), [screenshot](evidence/inspection-large.png)
- [wide report](evidence/inspection-wide.json), [screenshot](evidence/inspection-wide.png)
- [switch/failure report](evidence/inspection-switch.json), [screenshot](evidence/inspection-switch.png)

The installed CLI also passed `uv run datelier /tmp/datelier-cli.csv
--smoke-frames 30` and `uv run datelier --smoke-frames 30`: each rendered 30
frames and exited. The CLI fixture has two rows and one missing numeric value.

### Component and background-job benchmarks

```sh
POLARS_MAX_THREADS=8 uv run scripts/benchmark_inspection.py
```

Three fresh processes per case exercise the actual importer, schema/first page,
last page, and background loading contract. Each checks complete CSV values,
all source IDs/null counts, page bounds, and source metadata preservation. Peak
RSS includes the generated table, two imported datasets, and validation.
CSV's user `row_id` infers as Int64; separate source IDs are UInt64. Files are
written immediately before reading, so page caching is expected. These are
not cold-disk measurements.

| Rows × columns | CSV + prepared ms | Schema + first page ms | Last page ms | Background to prepared ms | Peak RSS MiB |
| --- | ---: | ---: | ---: | ---: | ---: |
| 10k × 8 | 2.43 | 1.08 | 0.71 | 4.50 | 80.47 |
| 100k × 8 | 6.25 | 1.53 | 0.96 | 7.23 | 124.86 |
| 1m × 8 | 29.37 | 1.48 | 0.94 | 34.67 | 517.89 |
| 100k × 66 | 29.69 | 4.27 | 2.50 | 34.22 | 488.60 |

These are medians. Numeric assertions against all 12 saved measurements pass
≤1 s narrow / ≤2 s wide loading, ≤50 ms page, ≤250 ms summary, and ≤1 GiB RSS
budgets. GUI reports separately pass ≤33 ms frame p95, applicable
loading-to-visible budgets, and ≤1 GiB RSS. Final measurements ran without
concurrent Datelier tests, benchmarks, or GUI probes.

[Raw evidence](evidence/inspection-benchmark.json) records Intel i7-13620H,
16 logical CPUs, 31.0 GiB RAM, Linux 7.0.0-34, CPython 3.14.7, eight Polars
threads, and Polars 1.44.2 / ImGui Bundle 1.92.900 / NumPy 2.5.3. Fixtures
have six (wide: 64) Float64 features, a String category, and a null every 17
rows in the last feature. GUI rendering uses Phase 0's verified Mesa software
renderer; accelerated rendering remains unverified. These fixtures demonstrate
budgets on this machine, not universal capacity.

Final implementation/milestone checks:

```text
uv run pyrefly check          0 errors
uv run pytest                48 passed in 9.44s
uv run ruff check .          passed
uv run ruff format --check .  32 files formatted
uv lock --check --offline    passed; 24 packages
git diff --check             passed
```

The full suite uses M1.1's thread/cache environment. M1.1 and M1.2 exit gates
pass; Phase 1 is complete. Phase 2 format coverage is next.

## Completed step commits

| Commit | Verified step |
| --- | --- |
| `cd69ef1` | Dataset identity and revision isolation |
| `7c65f4f` | CSV options, diagnostics, failure and preservation tests |
| `6eeb5ee` | M1.1 evidence and gate recording |
| `c717b5c` | Background loading and prepared inspection |
| `2609a9e` | Virtualized preview, schema and status controls |
| `31bdccd` | Lifecycle, CLI, performance gates and GUI evidence |
