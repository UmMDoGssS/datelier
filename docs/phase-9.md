# Phase 9 — Editor sessions verification

The next authorized phase is Phase 9 in [ROADMAP.md](../ROADMAP.md).
Its entry prerequisites are the completed M7.2 local installation and the
verified package refactor (through `0879793`). The starting tree was clean at
`516ccb8`. Existing workspace compatibility tests are available.

## Implementation steps and gates

1. Isolate file-owned inspection controllers and publication; establish one
   bounded application worker pool with independently closable job owners.
2. Add application-owned tab order/activation, native top tabs, reorder/close/New
   Tab, and active-file docking callbacks. Verify loading/analysis closure and
   repeated-tab resources before completing M9.1.
3. Add Welcome, multiple file selection/folder listing, duplicate focus, recent
   files/workspaces, contextual import controls and workspace menu actions.
   Verify recovery and native opening workflows for M9.2.
4. Add versioned whole-session recipes, legacy migration, atomic saves,
   independent restore/relink outcomes and fresh-process layout/view recovery.
   Verify that restoration starts no ML for M9.3.
5. Prepare and render explicitly mapped cross-file numeric/category profiles,
   common bins/order and count/density scales; persist comparison settings and
   preserve source-bound selections. Verify native training/test comparisons,
   fresh-process restoration, full regression and multi-file resource budgets
   before completing M9.4 and Phase 9.

Every implementation step runs Pyrefly, focused tests, Ruff lint/format,
applicable native GUI smoke, diff review and a coherent step commit. Each
milestone additionally requires the full suite and recorded acceptance evidence.
All Phase 9 exit gates remain open until evidence is recorded below.

## Step 1 — File ownership and shared workers

`FileSession` owns the loader, pipeline/editor, table/pages, selection,
exploration, analysis and per-file recipe controls. Its stable session ID is
independent of dataset revision. Frames poll this prepared state; application
preferences are borrowed defaults. The existing `GuiSession` smoke-hook name
remains an alias so preceding GUI acceptance scripts still exercise the app.

GUI controllers use one four-worker pool with at most 64 outstanding jobs.
Capacity failures are visible retryable errors. Each controller tracks its own
futures, cancels its queued work on closure, and cannot shut down sibling jobs.
Executing imports/edits can finish after abandonment; closing a file blocks its
publication without waiting in a frame. Analysis cancellation requests worker
termination; application shutdown waits for pool cleanup and explicit writes.
Standalone controllers retain private executors for existing CLI/tests.

Verification on 2026-10-06, Linux/Python 3.14.7:

- 51 focused tests pass, covering shared capacity/owner closure and two-file
  history, equal row IDs, selections, controls, undo, and loading-tab closure,
  plus existing loader/page/edit/analysis/workspace/preferences regressions.
- Batch Pyrefly reports zero errors; Ruff lint and format checks pass;
  `git diff --check` passes.
- Native `scripts/workspace_smoke.py` passes on Mesa software OpenGL: 31 save
  frames / 46 reopen frames, missing-source relink, restored unfitted settings,
  redo and linked selection, zero implicit ML, and preserved source bytes.
  This existing smoke drives controls through frame hooks, not physical clicks.
  The sandbox cannot access display `:0`; the native command ran with desktop
  access. No accelerated renderer or other platform claim is made.

Commands use `UV_CACHE_DIR=/tmp/datelier-uv-cache uv run --offline`:
`pytest tests/test_shared_jobs.py tests/test_file_sessions.py tests/test_loading.py
tests/test_preview.py tests/test_editing.py tests/test_analysis_jobs.py
tests/test_workspace_restore.py tests/test_preferences.py` with
`POLARS_MAX_THREADS=8`; `pyrefly check`; `ruff check .`; `ruff format --check .`;
and `LIBGL_ALWAYS_SOFTWARE=1 POLARS_MAX_THREADS=8 uv run --offline
scripts/workspace_smoke.py`. Native tabs/full suite/lifecycle resources remain
the next M9.1 gates.

Step 1 committed as `c0d0fbe`.

## Step 2 — Editor tabs and active-file docking

`EditorSession` owns tab order/activation, preferences and the shared pool.
Each file is polled independently, including while inactive. A native edge
toolbar provides switching, drag reordering, close buttons/middle-click closure,
and New Tab; closing the last tab leaves a blank Welcome tab. Stable native IDs
distinguish duplicate filenames and survive loading/analysis status changes.
Panel callbacks look up the active file when rendered. Per-file ImGui ID scopes
and panel scroll positions keep table/plot/control state independent.

Verification on 2026-10-06:

- Two editor-model tests cover reorder/activation/closure, last-tab replacement,
  rejected closed IDs/invalid orders and duplicate filenames. Seven focused
  file/shared-worker/editor tests pass. Full suite: **500 passed in 15.75s**.
- Pyrefly zero errors; Ruff lint/format and diff whitespace checks pass.
- The existing native workspace smoke passes again: 31 save / 48 restore frames.
- `scripts/editor_tabs_smoke.py` passes in **191 frames** with synthetic ImGui
  button/position/delta input applied before the toolbar renders: native switch,
  drag reorder, middle-click close, New Tab and docked active-file data; independent
  history, selections, bins/seeds, inactive-file PCA completion and source bytes.
  This verifies native input/state; physical mouse use is not claimed.
- [Native editor screenshot](evidence/phase9/editor-tabs.png) records the test
  dataset beside its independent Welcome tab and selected source row.

The step uses the same Pyrefly/Ruff/full-suite commands as Step 1, plus
`LIBGL_ALWAYS_SOFTWARE=1 POLARS_MAX_THREADS=8 uv run --offline
scripts/editor_tabs_smoke.py`. M9.1 closure/resource acceptance remains open.
