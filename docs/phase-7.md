# Phase 7 verification evidence

Datelier is a simple personal tool. This phase checks the existing workflow and
local Linux installation. Version 0.1.0 remains the personal-use package version;
no public publishing, installer service or release automation is required.

## M7.1 — Complete workflows and reliability

Verified on 2026-10-04 with Linux x86_64, Python 3.14.7, an Intel i7-13620H,
16 logical CPUs, 31 GiB RAM, Polars 1.44.2, ImGui Bundle 1.92.900 and NumPy 2.5.3.
Resource runs use eight Polars threads, one BLAS/OpenMP thread and Mesa software
OpenGL. Measurements run sequentially in fresh processes. Generated data remains
temporary. Existing phase budgets and analysis sample limits remain in force.

`tests/test_complete_workflow.py` exercises CSV, TSV, JSON, JSONL, Parquet and XML:
import → preview → filter/sort/derive → profiles/scatter → explicit PCA → linked
selection → save an undo cursor → reopen/redo → explicit rerun → CSV/Parquet export.
The Parquet fixture additionally covers t-SNE, UMAP and k-means. Assertions cover
null exclusion, sampling, provenance, source identity independent of sorted
position, stale embedding/selection rejection, exact recipe settings and source
bytes. Unicode paths, multiline text, XML escaping and an empty filtered
workspace are included. Fitted results remain session-only.

The added abrupt-worker-exit test checks that the prior analysis remains usable
and a subsequent run succeeds. It found an empty failure detail when a worker
closed its result pipe. The corrected message reports the worker exit code.
Existing tests retain malformed/nested inputs, nonfinite/constant data, expression
restrictions, failed edits, cancelled/stale jobs, source aliases, changed sources,
failed redo recipes and corrupt settings coverage.

`scripts/workflow_smoke.py` runs two fresh GUI processes. The first transforms a
48-row CSV, displays a linked PCA embedding, fits k-means and saves settings/history.
The second reopens, checks exact values/source IDs/settings, selects the same row,
exports both formats and verifies source replacement is rejected. Reopening runs
no ML. The [report](evidence/phase7-workflow.json) records 233 save frames and
28 reopen frames, 14.29/13.07 ms frame p95, and a combined peak upper bound under
715 MiB. [Save](evidence/phase7-workflow-save.png) and
[reopen](evidence/phase7-workflow-reopen.png) screenshots were visually inspected:
the transformed table, profiles, linked plots, restored seed/features and
source-protection message render correctly. Actions use frame hooks; physical
button clicks are not claimed.

All six `scripts/format_smoke.py` GUI regressions pass 90 frames each, including
prepared values/nulls/source IDs and a visible failed import retaining active
data. JSON/JSONL/XML show nested-input diagnostics; XML also uses namespaced
extraction controls. [Compact report](evidence/phase7-format-gui.json).

Fresh performance checks use 10k/100k/1m × 8 and 100k × 66 fixtures: one source-ID
column, six or 64 numeric columns, a category, and regular missing values.

| Check | Observation | Retained budget |
| --- | ---: | ---: |
| CSV import + prepared preview (12 runs) | max 75.09 ms | 1 s narrow / 2 s wide |
| Background CSV import + prepared preview | max 53.97 ms | 1 s narrow / 2 s wide |
| Preview page / basic summary (CSV) | max 0.67 / 1.23 ms | 50 / 250 ms |
| Default / expanded dashboard | max 127.22 / 59.21 ms | 2,000 / 4,000 ms |
| Numeric comparison | max 319.81 ms | 4,000 ms |
| Transformed replay | max 23.46 ms | recorded, no separate time budget |
| Explicit CSV / Parquet export | max 30.25 / 9.26 ms | recorded, no separate time budget |
| Inspection/transform/exploration peak RSS | max 766.03 MiB | 1,024 MiB |

Reports: [CSV inspection](evidence/phase7-inspection.json),
[transforms/export](evidence/phase7-operations.json),
[exploration](evidence/phase7-exploration.json),
[other formats](evidence/phase7-formats.json). All 20 non-CSV format runs pass
the 250 ms summary, 50 ms page and 1 GiB process budgets. Million-row JSON/JSONL/XML
imports take 8.17/9.66/12.49 seconds; they do not inherit CSV's one-second budget.
The largest non-CSV RSS is 768.70 MiB (wide XML).

The live million-row fixture runs all four explicit analysis jobs at default
sample limits: PCA/k-means 10,000, t-SNE 2,000 and UMAP 5,000. Its
[report](evidence/phase7-analysis-large.json) passes 17.46 ms frame p95 and
1,541.61 MiB combined parent/child upper bound (budgets 33 ms / 2,048 MiB).
The [wide 100k × 66 run](evidence/phase7-analysis-wide.json) passes 17.96 ms and
1,386.30 MiB at the same default sample limits with 64 analysis features.
The child RSS counter is a conservative process high-water mark; summing peaks
does not measure simultaneous resident memory. Algorithm wall times are recorded,
not promised; UMAP includes library initialization. These are fixture measurements,
not universal capacity guarantees. Accelerated rendering and other platforms
remain unverified.

Reproduction (prepend `UV_CACHE_DIR=/tmp/datelier-uv-cache` and use `--offline`
in the restricted workspace; GUI commands need access to the desktop display):

```sh
POLARS_MAX_THREADS=8 OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 uv run pytest
uv run pyrefly check
uv run ruff check .
uv run ruff format --check .
POLARS_MAX_THREADS=8 uv run scripts/benchmark_inspection.py
POLARS_MAX_THREADS=8 uv run scripts/benchmark_operations.py
POLARS_MAX_THREADS=8 uv run scripts/benchmark_exploration.py
POLARS_MAX_THREADS=8 uv run scripts/benchmark_formats.py
LIBGL_ALWAYS_SOFTWARE=1 POLARS_MAX_THREADS=8 OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 uv run scripts/workflow_smoke.py
LIBGL_ALWAYS_SOFTWARE=1 POLARS_MAX_THREADS=8 OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 NUMBA_CACHE_DIR=/tmp/datelier-numba-cache uv run scripts/benchmark_analysis_gui.py --output /tmp/datelier-analysis-large.ppm
LIBGL_ALWAYS_SOFTWARE=1 POLARS_MAX_THREADS=8 OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 NUMBA_CACHE_DIR=/tmp/datelier-numba-cache uv run scripts/benchmark_analysis_gui.py --rows 100000 --columns 64 --output /tmp/datelier-analysis-wide.ppm
```

Final milestone checks: **344 tests passed in 16.35s**, batch Pyrefly zero errors,
Ruff lint/format and diff whitespace checks passed. M7.1 passes.

Completed steps: `3e946d1` (complete workflow tests), `1ff0298` (worker-exit detail),
`e11158e` (fresh-process GUI workflow and resource evidence).

## M7.2 — Local Linux installation

`uv build --offline` produces `dist/datelier-0.1.0.tar.gz` and
`dist/datelier-0.1.0-py3-none-any.whl`; the wheel is built from the source archive.
No dependency or build configuration changes were needed. The wheel contains
every Python module in `src/datelier`, the `datelier = datelier:main` entry point,
the current README, version 0.1.0 and Python >=3.14 metadata. The archive's README
matches too. Neither contains generated bytecode. The
[artifact report](evidence/phase7-package.json) records sizes, SHA-256 hashes,
installed package path and exact runtime versions. Build outputs are ignored by
Git and can be recreated; nothing was published.

Created an empty environment at `/tmp/datelier-phase7-linux` using the reference
Python interpreter. Installed 15 locked runtime dependencies with
`uv sync --locked --no-dev --no-install-project`, then the built wheel with
`uv pip install --no-deps`. `uv pip check` confirms all 16 packages are compatible;
pytest, Ruff and Pyrefly are absent from this runtime environment. Dependency
downloads were reused from the cache; a fresh network download was not tested.
The offline pip requirements resolver could not discover several cached wheels;
syncing from the lock's exact URLs succeeded. The README uses the verified sync
procedure for the separate local install.

Ran from `/tmp`, with a copy of `scripts/workflow_smoke.py` outside the repository
and no source-path injection. Both fresh GUI processes loaded
`/tmp/datelier-phase7-linux/lib/python3.14/site-packages/datelier/__init__.py`.
The [installed workflow](evidence/phase7-installed-workflow.json) passes import,
preview, sort/filter/derived column, plots, explicit PCA/k-means, linked selection,
workspace save/reopen, both exports and source protection. It records 295 save /
28 reopen frames, 14.59/13.32 ms p95 and less than 697 MiB combined RSS upper bound.
Reopen starts no analysis. The installed `datelier --help`, dataset launch (60
frames), `--workspace` launch (60 frames) and empty window (20 frames) all exit
successfully on Mesa software OpenGL.

Reproduction from the checkout, with an empty environment path:

```sh
uv build
UV_PROJECT_ENVIRONMENT=/tmp/datelier-install uv sync --locked --no-dev --no-install-project
uv pip install --python /tmp/datelier-install/bin/python --no-deps dist/datelier-0.1.0-py3-none-any.whl
uv pip check --python /tmp/datelier-install/bin/python
cp scripts/workflow_smoke.py /tmp/datelier-installed-workflow.py
cd /tmp
LIBGL_ALWAYS_SOFTWARE=1 POLARS_MAX_THREADS=8 OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 /tmp/datelier-install/bin/python /tmp/datelier-installed-workflow.py
/tmp/datelier-install/bin/datelier --help
```

The verification run used `UV_CACHE_DIR=/tmp/datelier-uv-cache` and `--offline`
for uv commands. GUI commands ran with desktop display access. This checks an
isolated virtual environment on the reference Linux machine, not a new OS image.

Personal-use acceptance checklist:

- [x] All earlier v1 capability gates and M7.1 hardening pass.
- [x] Wheel/source archive build, package contents and metadata are consistent.
- [x] Clean runtime install and dependency compatibility check pass.
- [x] CLI help, dataset, workspace and empty GUI launch modes pass.
- [x] Installed-package complete workflow and source/identity invariants pass.
- [x] README setup and first-session instructions match tested controls/actions.
- [x] Final application checks: 344 tests, Pyrefly zero errors and Ruff pass,
  as recorded for M7.1; no application code changed afterward.
- [x] Markdown local links and diff whitespace checks pass.
- [x] Scope remains personal/local; no unresolved required v1 items.

M7.2 and Phase 7 pass. The first-session walkthrough is documented in the README;
the live verification uses frame hooks rather than physical clicks. Version 0.1.0
is retained, and only Linux/Python 3.14.7/Mesa software rendering are verified.
Phase 8 remains optional investigation requiring a concrete personal-use need.
Commit `b6d201d` records the installation/first-session instructions; the final
acceptance evidence and checklist are committed with this gate.
