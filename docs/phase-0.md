# Phase 0 evidence

Recorded on 2026-10-04. This is feasibility evidence for Linux, not a v1
capacity or platform-support guarantee.

## M0.1 development baseline

The clean environment at `/tmp/datelier-baseline-env` was created with
`UV_PROJECT_ENVIRONMENT=/tmp/datelier-baseline-env uv sync --locked`.
CPython 3.14.7 was selected. The dev group installed Pyrefly 1.3.2, pytest 9.1.1,
and Ruff 0.16.10. Its `datelier` entry point printed `Hello from datelier!`
and exited successfully. Imports of all three dev tools passed.

Step checks:

```text
uv run pyrefly check          INFO 0 errors
uv run pytest                1 passed in 0.02s
uv run ruff check .          All checks passed!
uv run ruff format --check .  5 files already formatted
git diff --check             passed
```

Commands in this environment used `UV_CACHE_DIR=/tmp/datelier-uv-cache` because
the default cache is outside the writable sandbox. PyPI downloads ran with
approved network access; subsequent checks ran in the sandbox.

## M0.2 dependency installation

`uv add polars imgui-bundle numpy scikit-learn umap-learn` resolved and installed
Linux wheels on CPython 3.14.7. The lockfile records ImGui Bundle 1.92.900,
Polars 1.44.2, NumPy 2.5.3, scikit-learn 1.9.1, UMAP 0.5.12, SciPy 1.18.1,
Numba 0.68.0, llvmlite 0.50.0, and pynndescent 0.6.0.

All five direct runtime imports passed without creating a GUI. Step checks:
Pyrefly: 0 errors; full pytest: 6 passed in 10.69s; Ruff lint: passed; Ruff
format: 7 files already formatted; `git diff --check`: passed.

## M0.2 GUI and conversion probe

```sh
LIBGL_ALWAYS_SOFTWARE=1 uv run scripts/gui_smoke.py
```

The command rendered 120 frames, with 118 successful ImPlot frames and
distinct nonzero dock IDs (preview: 1, scatter: 2). The 256-row fixture has
eight columns; the preview shows the first 12 rows and four columns. The plot
shows all 256 finite coordinate pairs. The captured final frame was visually
inspected: readable native table, two docked tabs, labeled axes, and the expected
three synthetic groups. [Screenshot](evidence/gui-smoke.png) and
[raw timing/docking evidence](evidence/gui-smoke.json) are retained. Frame
interval p95 after ten warmup frames was 10.83 ms.

The session uses Wayland with Xwayland display `:0`. OpenGL inspection
(`glxinfo -B`) reports Mesa 26.0.8 and Intel RPL-P graphics. The default
accelerated probe stalled and was stopped; the successful probe uses
`LIBGL_ALWAYS_SOFTWARE=1`. Accelerated rendering is not claimed verified.
The sandbox cannot access the display socket, so GUI runs required approved
display access. This does not affect headless domain tests.

`prepare_scatter` selects only row identity and two numeric columns, excludes
null/nonfinite pairs, and takes at most 2,000 eligible rows before NumPy
conversion. It retains source IDs independently of position and labels the
displayed/eligible/source counts. Tests cover filtered identity, values,
numeric dtype, empty inputs, deterministic mixed fixtures, and rejected
coordinates/limits. No analysis runs on GUI load.

Step checks: Pyrefly: 0 errors; focused pytest: 5 passed in 0.15s; Ruff lint:
passed; Ruff format: 13 files already formatted; `git diff --check`: passed.
The bounded exit uses the active runner parameters; callbacks hold prepared
preview strings and plot arrays, with no table-wide work inside a frame.

## M0.2 analysis compatibility

```sh
OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 NUMBA_CACHE_DIR=/tmp/datelier-numba-cache \
  uv run scripts/analysis_smoke.py
```

The fixture has 64 rows and three Float64 features. Four periodic-null rows
are excluded; standard scaling converts only the selected finite feature
matrix. IDs preserve the original order. Seed 42 and explicit settings are
recorded in [the result report](evidence/analysis-smoke.json).

| Algorithm | Output shape | Output dtype | Finite | Run seconds |
| --- | --- | --- | --- | --- |
| PCA | 60 × 2 | Float64 | yes | 0.0004 |
| t-SNE | 60 × 2 | Float32 | yes | 0.0379 |
| UMAP | 60 × 2 | Float32 | yes | 4.8688 |
| k-means | 60 labels | Int32 | yes | 0.0119 |

These are compatibility timings after imports, not throughput guarantees.
UMAP's timing includes first-fit JIT compilation in the process. Probes are
only invoked by explicit commands/tests. The GUI imports no analysis modules.
Tests additionally verify three separated k-means groups, dominant first PCA
variance, excluded NaN/null row alignment, standardized means, and rejection
of too few eligible rows.

Step checks: Pyrefly: 0 errors; focused pytest: 6 passed in 9.24s; Ruff lint:
passed; Ruff format: 16 files already formatted; `git diff --check`: passed.

## M0.2 performance baseline and budgets

Reference hardware: Intel Core i7-13620H, 16 logical CPUs, 31.0 GiB physical
RAM; Linux 7.0.0-34, x86_64, glibc 2.43; CPython 3.14.7. The table benchmark
fixes Polars to eight threads. Dependency versions and machine metadata are
also in [the raw benchmark report](evidence/benchmark.json).

```sh
POLARS_MAX_THREADS=8 uv run scripts/benchmark_feasibility.py \
  --output /tmp/datelier-benchmark.json
POLARS_MAX_THREADS=8 LIBGL_ALWAYS_SOFTWARE=1 uv run scripts/gui_smoke.py \
  --rows 1000000 --frames 180 --output /tmp/datelier-gui-large.ppm
POLARS_MAX_THREADS=8 LIBGL_ALWAYS_SOFTWARE=1 uv run scripts/gui_smoke.py \
  --rows 100000 --numeric-columns 64 --frames 180 \
  --output /tmp/datelier-gui-wide.ppm
```

Each table measurement runs in a fresh process, three repeats per case.
The final measurements ran without other Datelier benchmark or GUI jobs.
Fixtures use UInt64 row identity, six (wide: 64) Float64 features, and a
three-value String category. The last feature has a null every 17 rows.
The deterministic formula is in `feasibility/fixtures.py`; generated data
and CSV files are temporary and are not committed.

CSV is written immediately before reading, so filesystem page caching is
expected. These are local parsing/processing measurements, not cold-disk
I/O claims. Preview preparation converts the first 100 rows/eight columns
to strings; summaries compute null counts and numeric means. CSV roundtrip
equality and bounded plot row identity are checked in every worker.
RSS is Linux process peak memory, including imports, generation, the original
and reloaded table, CSV mapping, conversion, and validation; it is not a
measurement of a finished application. GUI timings are frame intervals,
excluding the first ten warmup frames, with no input latency simulation.

Medians across three processes (milliseconds except peak RSS):

| Rows × columns | Generate | CSV read | Preview | Summaries | Plot preparation | Peak RSS MiB |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 10k × 8 | 11.63 | 2.88 | 13.21 | 0.20 | 13.26 | 91.43 |
| 100k × 8 | 19.68 | 12.47 | 7.27 | 0.37 | 0.96 | 131.18 |
| 1m × 8 | 82.59 | 26.76 | 1.37 | 1.42 | 1.64 | 480.79 |
| 100k × 66 | 48.56 | 25.41 | 4.13 | 1.67 | 2.95 | 435.60 |

The plot boundary holds 2,000 points in three arrays totaling 48,000 bytes.
An initial 10,000-point run with four-pixel markers produced frame p95 values
of 73.34 ms (1m) and 69.54 ms (wide); those exploratory runs overlapped table
benchmark work, so the comparison is directional, not a controlled speedup.
Raw initial evidence: [1m](evidence/gui-large-10000.json),
[wide](evidence/gui-wide-10000.json). Reproduce that cap with
`scripts/gui_smoke.py --point-limit 10000` (the final smaller marker style is
still used). The default cap was reduced to 2,000, with two-pixel markers and
no marker outline, to bound software-renderer overdraw.

Final GUI runs both rendered 180 frames, 178 plot frames, and dock IDs 1/2:
1m fixture p95 **12.50 ms**, wide fixture p95 **12.97 ms**. Screenshots were
visually inspected for readable previews, labeled truncation, docked panels,
and finite plotted coordinates. Final evidence:
[1m screenshot](evidence/gui-large.png), [1m timings](evidence/gui-large.json),
[wide screenshot](evidence/gui-wide.png), [wide timings](evidence/gui-wide.json).

Acceptance budgets for later milestones on this reference environment,
established from this baseline before judging later implementation:

| Gate | Budget | Phase 0 observation |
| --- | --- | --- |
| CSV read + first prepared preview, up to 1m × 8 | ≤ 1 s | all repeats pass |
| CSV read + first prepared preview, 100k × 66 | ≤ 2 s | all repeats pass |
| Prepared 100-row preview page | ≤ 50 ms | maximum 13.33 ms |
| Basic null/mean summaries | ≤ 250 ms | maximum 4.27 ms |
| Two-column finite filtering + plot preparation | ≤ 100 ms | maximum 13.38 ms |
| Default scatter boundary | ≤ 2,000 points / 48,000 array bytes | all cases pass |
| GUI frame interval p95, software renderer | ≤ 33 ms | 12.50 / 12.97 ms |
| Peak benchmark process RSS | ≤ 1 GiB for these fixtures | maximum 480.98 MiB |

Future preview/job gates must measure loading-to-visible behavior, background
work, virtualization, and actual input response; these probes only establish
component budgets. Wider/type-heavy data and different hardware require new
measurements. Only 60 eligible rows were tested for ML; table/plot budgets do
not establish large-input analysis capacity. Analysis probes are explicitly
bounded to 64 source rows; t-SNE uses 500 iterations and UMAP 100 epochs.
Later ML gates must establish visible sampling/limits with measurements.

The second clean environment `/tmp/datelier-phase0-env` passed
`uv sync --locked --offline`, installed all 23 runtime/dev distributions,
launched `datelier --help`, and imported the full stack. The offline sync
used the approved-download cache, not an existing environment.

Final step and milestone checks:

```text
uv run pyrefly check          INFO 0 errors
uv run pytest                17 passed in 9.33s
uv run ruff check .          All checks passed!
uv run ruff format --check .  17 files already formatted
uv lock --check --offline    Resolved 24 packages; passed
git diff --check             passed
```

The full test command used `OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1` and
`NUMBA_CACHE_DIR=/tmp/datelier-numba-cache`. Numeric assertions against the
saved reports confirmed that all 12 table runs and both final GUI runs meet
every applicable component budget above. Timing collection is limited to
bounded smoke runs; interactive sessions do not accumulate timing samples.

## Completed step commits

| Commit | Verified step |
| --- | --- |
| `768a8c6` | Python 3.14 metadata, development tools, clean CLI baseline |
| `97f2f08` | Locked runtime dependency set and import compatibility |
| `fe81f8b` | Prepared Polars preview/plot, docking, and GUI smoke evidence |
| `a2c737c` | Explicit PCA/t-SNE/UMAP/k-means compatibility and row alignment |
| `1e4cc32` | Synthetic benchmarks, budgets, and bounded scatter rendering |

M0.1 and M0.2 exit gates pass. Phase 0 is complete; the next outstanding gate
is M1.1 (CSV import and dataset state). No later application milestones are
claimed complete.
