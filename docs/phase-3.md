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

M3.1 passes. M3.2 and the phase exit remain open.
