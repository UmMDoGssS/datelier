# Phase 4 verification evidence

## M4.1 Type-aware profiles and automatic plots

Entry: Phase 3 passed. The worktree and current implementation were inspected.
`345a45e` adds bounded type-aware profiles; `4b144cb` adds plot preparation and
background lifecycle; `8bc4d29` renders the automatic dashboard. Each step
passed its focused tests, batch Pyrefly, Ruff lint/format, and diff checks
before its commit. The UI step also passed a live Linux smoke check.

Numeric profiles report null/nonfinite counts, finite range/mean, and exact
Polars histograms. Temporal profiles report their range and physical-unit
histograms. Categorical profiles report deterministic top counts, distinct
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

M4.1 passes. M4.2 and the Phase 4 exit remain open.
