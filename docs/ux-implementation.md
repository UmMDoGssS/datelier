# Inspection UX implementation

Started 2026-10-04 from the [Titanic review](ux-titanic-review.md), following its
ordered repair sequence. Existing v1 feature gates remain unchanged. Each
implementation slice is verified and committed before the next one starts.

## Step 1 — Understandable single-column charts (in progress)

### 1a — Correct profile coordinates and labels

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

Step 1 remains open until the ordinary single-column Histogram/KDE/ECDF/Box/
Violin selector and compact quality summary are verified. Plot sizing, unified
analysis, styling, roles/grouping, direct table actions, and file dialogs remain
subsequent slices in the review plan.
