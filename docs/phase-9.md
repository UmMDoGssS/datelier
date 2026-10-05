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
M9.1 passes with the evidence below. M9.2–M9.4 and Phase 9 remain open.

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

## Step 3 / M9.1 exit — Closure and resource cleanup

Closing a file releases its inspection/pipeline, preview pages, embedding plots
and fitted analysis results. Closed caches/jobs reject later publication and
new preparation. Native tab bookkeeping drops closed IDs. Cancelling a spawned
analysis is asynchronous during tab closure; application shutdown waits for
worker cleanup. Explicitly requested exports retain their existing write
semantics. Switching tabs never launches ML.

Verification on 2026-10-06:

- **14 focused tests** pass. An executing spawned analysis is observed through
  its live process/future, its tab closes in under 0.5 s without waiting for the
  ten-second fixture, the future reports cancellation and its process is
  removed from active children; a sibling remains usable. An executing preview
  completes after closure without repopulating its closed cache. Existing
  loading/obsolete-result, independent history and selection fixtures pass.
- Full suite: **502 passed in 17.39s**. Pyrefly zero errors; Ruff lint/format and
  diff checks pass. Native tab smoke passes again in **194 frames**. The saved
  Step 2 screenshot was visually inspected: distinct test/Welcome tabs, selected
  source row 2, test-file schema/profile and independent seed 19 render correctly.
- `scripts/benchmark_editor_tabs.py` declares budgets before running: <=2 s
  metadata/prepared preview, <=33 ms frame p95 and close, <=1 GiB process peak
  RSS, <=96 MiB retained growth after warmup, and at most four shared workers.
  Fixtures: two Parquet files, each 100,000 rows and eight float columns with
  different names/scales; 30 additional open/render/close cycles. Both files
  stay usable. [Recorded resource report](evidence/phase9/tab-lifecycle.json):
  387 frames; initial previews 124.7/159.5 ms; maximum cycle preview 204.4 ms;
  frame p95 15.21 ms; peak RSS 460.84 MiB; retained growth -1.86 MiB; maximum
  closure 0.224 ms; two shared workers observed (four allowed). Zero outstanding
  jobs and zero retained closed sessions after GC; zero worker threads after
  app exit. Source bytes match; 1,573,727 fixture bytes and the temporary
  directory are removed at exit. This is a fixture-specific measurement, not
  a capacity guarantee for arbitrary widths/types or unlimited tabs.

Commands: the focused tests plus `POLARS_MAX_THREADS=8 uv run --offline pytest`,
Pyrefly/Ruff/diff checks, and the existing native tab smoke. The new resource
command is `LIBGL_ALWAYS_SOFTWARE=1 POLARS_MAX_THREADS=8 uv run --offline
scripts/benchmark_editor_tabs.py`; all uv commands use the temporary cache
setting recorded above. Mesa/Linux remains the verified renderer/platform.

M9.1 passes. Step commits are `c0d0fbe` (file/shared ownership), `ec76f42` (tabs),
and the closure/evidence commit accompanying this section. M9.2 is next; the
Open dataset and Workspace panels remain until its editor-controls replacement.
Whole-session workspace restoration and cross-file profiles remain M9.3/M9.4.

## Step 4 / M9.2 in progress — Welcome and file opening

Blank tabs render Welcome with Open Files, Open Folder and a path/retry action.
An ImGui modal picker renders virtualized directory metadata prepared in shared
workers; folder listing and symlink/path resolution never run in frame callbacks.
Selections can span folders; Open Folder can open all supported immediate files.
The picker currently lists the existing tabular formats; direct media collections
remain M10.4. Directory navigation/failures have parent/retry controls.

Open requests are bound to their originating tab. Multiple chosen paths reuse
its blank tab and create independent additional tabs. Canonical paths deduplicate
choices, including symlink aliases, and focus already-open sources without
reimporting or resetting their state. A failed import has its own Welcome/error
state and can retry with explicit import options. Closing the origin abandons
path resolution and closes its picker without routing results to a replacement.

Verification on 2026-10-06: **18 focused tests** pass across opening/catalog,
file/editor ownership, shared workers and CLI behavior. Fixtures include malformed
CSV, retry delimiter options, symlink/duplicate choices, unsupported files,
missing folders, newer directory listings, and closing an executing resolution.
Batch Pyrefly zero errors; Ruff lint/format and diff whitespace checks pass.
Native `scripts/welcome_smoke.py` passes **126 frames / 101 Welcome frames**: startup
and New Tab, multi-checkbox selection, supported folder listing/open-all, duplicate
focus with unchanged revisions, unchanged source bytes and zero implicit ML.
Input uses ImGui synthetic button/position/delta state before rendering.

The smoke's `--capture welcome` and `--capture picker` modes produce visual
artifacts without claiming the multi-open gates: 12/28 frames respectively.
[Startup Welcome](evidence/phase9/welcome.png),
[file picker](evidence/phase9/file-picker.png), and
[opened files](evidence/phase9/welcome-files.png) were visually inspected.
The picker displays the two tabular fixtures, excludes the text fixture, and
shows independent selection/open/cancel controls; the opened train tab displays
its own rows/schema/profile beside the test tab.

Commands retain the temporary uv cache setting and Mesa/Linux native invocation
from earlier steps. Focused command: `pytest tests/test_opening.py
tests/test_editor_sessions.py tests/test_file_sessions.py tests/test_shared_jobs.py
tests/test_cli.py`. Native command: `LIBGL_ALWAYS_SOFTWARE=1 POLARS_MAX_THREADS=8
uv run --offline scripts/welcome_smoke.py`; capture modes add `--capture welcome`
or `--capture picker` and `--output /tmp/<name>.ppm`.

M9.2 remains open: recent files/workspaces and contextual import/workspace menu
actions must replace the old Open dataset/Workspace panels. Its full suite and
layout/menu/recent-source recovery acceptance remain to be recorded.


## Step 5 / M9.2 in progress — Recent sources and exact import settings

Preferences now retain up to 20 recent file/workspace references in most-recent
order. File entries retain their successful format/options; edits do not promote
an entry, and reopening an existing source focuses/promotes it without replay.
Invalid recent entries recover independently of theme/layout/view preferences.
Import controls bind exact successful recipes, preserving literal separators in
option values until the user changes the controls. Schema rendering now lives
in its own data module. Preference writes protect every open/requested source,
including inactive files and sources awaiting relinking.

Welcome renders recent entries and retains missing-file paths/settings for retry.
Recent workspace failures expose path/relink controls; successful saves/restores
enter the list. Whole-session recipes remain M9.3 work.

Verification on 2026-10-06: **42 focused tests passed in 0.82s** across recent
recipes, preferences, opening and legacy workspace restoration. Coverage includes
bounded MRU ordering, custom-delimiter reopening, section recovery, missing-file
retry with independent siblings, workspace source relinking, exact bound CSV,
JSONL, Parquet/XML options, and all-source preference protection. Pyrefly zero
errors; Ruff lint/format and diff checks pass.

Native `scripts/recent_smoke.py` launches separate save and reopen processes.
It clicks recent file/workspace entries, observes a moved-file failure, clicks
its path retry with the retained semicolon settings, and relinks the workspace
source. It verifies original source bytes and zero implicit ML. The save process
uses 16 frames; reopen uses 83 frames. [Recovered source](evidence/phase9/recent-recovery.png) is visually checked.
Input is synthetic ImGui input; source move and workspace relink are fixture/frame
hooks. Commands use the same uv cache/Mesa settings as earlier steps, focused
`pytest tests/test_recent_sources.py tests/test_preferences.py tests/test_opening.py
tests/test_workspace_restore.py`, Pyrefly/Ruff and native `scripts/recent_smoke.py`.

M9.2 remains open pending contextual editor/menu replacement, layout migration/
recovery and its full regression suite.
