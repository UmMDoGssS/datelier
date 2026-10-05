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
M9.1–M9.4 and Phase 9 pass with the evidence below. Phase 10 is next.

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


## Step 6 / M9.2 exit — Editor menus and contextual dialogs

File menus now expose New/Close Tab, Open Files/Open Folder, recent sources,
Import settings and Workspace actions. Source-bound import/workspace dialogs
replace the Open dataset/Workspace dock panels. Reimport explicitly resets the
owning tab's history only after a successful import; failures retain its last
usable data/recipe. The dialog retains its owner when active tabs change and
closes if its owner disappears. Blank-tab Welcome keeps workspace recovery
controls visible. Workspace writes protect sibling sources and aliases in the
worker, in addition to their own referenced source.

The left dock now contains Schema/profile interpretation controls. Older layouts
containing either removed panel recover to the new default layout with a visible
preferences message, retaining theme, plot/views and recent sources. Saved current
layouts still restore, reset and recover independently of the file recipes.
README opening/workspace instructions reflect the menu workflow.

Verification on 2026-10-06:

- **67 focused tests passed in 0.86s** for contextual reimport/failure retention,
  sibling-source write protection, legacy layout recovery, recent sources and
  existing preference/workspace behavior.
- **Full suite: 517 passed in 23.53s.** Batch Pyrefly zero errors; Ruff lint/format
  and diff whitespace checks pass.
- Native `scripts/editor_menu_smoke.py`: **285 frames**, synthetic clicks through
  File/import, workspace save/reopen, New Tab and Preferences/Reset layout;
  legacy-panel layout recovery, semicolon options, usable independent tabs,
  source bytes and zero implicit ML. Fixture values are entered through frame
  hooks; the native action buttons/menu items receive ImGui input. The smoke
  waits for the changing contextual form before choosing button coordinates.
- Fresh-process `scripts/preferences_smoke.py`: default restore 15 frames;
  save 21/reopen 68; saved dock/hide/theme restoration, reset and restore,
  independent workspace settings/history and linked selection pass.
- Existing native `scripts/workspace_smoke.py`: save 31/reopen 48; relink, redo,
  views and unfitted settings pass. Its recovery focuses Table preview/Welcome
  instead of the removed Workspace panel.
- Welcome smoke 126 frames, recent smoke 16/83, tab smoke 204 frames all pass
  after the topology change. Sources remain byte-identical. The
  [new native layout](evidence/phase9/editor-menu.png) was visually inspected:
  File menu, two independent custom-source tabs, schema and table/profile docks,
  and source-specific settings render without the two retired panels.

Commands retain the earlier offline uv/cache/Mesa settings; focused tests are
`tests/test_editor_controls.py tests/test_recent_sources.py tests/test_preferences.py
 tests/test_workspaces.py tests/test_workspace_restore.py`. The full suite and
all named native scripts run as separate commands/processes. Mesa/Linux remains
the verified renderer/platform. M9.2 passes; whole-session recipes/migration/
partial recovery and cross-file profiles remain M9.3/M9.4.


## Step 7 / M9.3 in progress — Version-two recipe and recovery foundation

A strict version-two session recipe stores ordered stable file IDs, active tab,
independent version-one file recipes, Welcome/source-draft tabs, source-bound
row selections, panel scroll positions, dock layout/hidden panels and typed
comparison mappings (labels/colors, bins/category limit, count/density scale).
Comparison preparation/rendering remains M9.4. Unloaded/failed direct sources
retain exact import drafts; saved recovery recipes retain their fingerprints and
operations when a source cannot reopen.

Storage shares bounded strict JSON parsing and atomic replacement with existing
workspaces. Paths are relative on disk and canonicalized in worker-side readers;
all referenced/requested sources and aliases are protected from overwrite. The
2 MiB recipe and 256 KiB dock-layout limits remain explicit errors. Existing
version-one files migrate to one-file sessions and resave as version two.

Prepared restoration returns a separate outcome per saved tab, retaining usable
files beside missing, changed or malformed sources. Relinking/changed-content
acceptance targets a saved file ID; foreign/duplicate recovery IDs are rejected.
Selections restore against that file's current source rows; unavailable IDs are
pruned and explicitly accepted changed content clears the selection. Replay
checks redo recipes, retains cursors and carries settings without fitted ML.

Verification on 2026-10-06: **79 focused tests passed in 0.95s** across new
session fixtures and prior workspace/preferences/recent/editor regressions.
Twelve new fixtures cover round trips with unequal row counts and independent
histories/seeds/views/IDs, layout/hidden panels and mappings; legacy migration;
portable source moves; good/missing/changed/malformed source recovery; selection
pruning; source/alias protection; failed atomic replacement with temporary-file
cleanup; 2 MiB rejection without altering the previous recipe; and invalid
session/recovery topology before import. Pyrefly zero errors; Ruff lint/format
and diff checks pass. Existing native workspace smoke passes again, save 31 /
reopen 47 frames, including relink, redo, view settings, source preservation and
zero implicit ML.

Commands use the earlier cache/offline/Mesa settings. Focused tests:
`tests/test_session_workspaces.py tests/test_workspaces.py
 tests/test_workspace_restore.py tests/test_editor_controls.py
 tests/test_preferences.py tests/test_recent_sources.py`; Pyrefly/Ruff/diff and
native `scripts/workspace_smoke.py`. The session APIs are a verified foundation;
the editor/menu/CLI still use version-one actions until the next implementation
step. M9.3 deliverables/exit/fresh-process/full-suite gates remain open.


## Step 8 / M9.3 in progress — Shared session jobs and editor publication

The editor now has typed whole-session save/open/recover APIs. Capture creates
immutable recipes and source references; workers fingerprint sources and perform
writes/import/replay. Restoring replaces owned file controllers while retaining
saved IDs/order/active tab, views, settings, history, selections and comparison
mappings. Welcome and failed-source tabs remain separate. Native tab bookkeeping
resets to saved order; panel bindings use weak controller references so a newly
restored controller with the same saved ID restores scroll without retaining a
closed session. Prepared layout/visibility remains pending for the next menu/CLI
integration step.

Session and recovery jobs share the bounded application executor. File revisions,
loader generations, edit state and open-request generations guard publication.
A closed recovery owner cannot publish into a new Welcome tab; an import begun
in a still-blank tab invalidates an earlier whole-session restore. Executing
abandoned work can finish, and explicit requested saves retain prior semantics.
Repeated successful workspace actions promote recent entries; recovery displays
its completed outcome. Session snapshots contain no tables or fitted artifacts.

Verification on 2026-10-06: **40 focused tests passed**, covering the new editor
save/reopen/partial-recovery APIs, worker-only fingerprinting, independent
histories/seeds/settings and source selections, closed recovery ownership and a
new import while a blank owner still has no revision, plus existing session,
file, opening and legacy workspace fixtures. Pyrefly zero errors; Ruff lint/format
and diff checks pass.

Native `scripts/session_workspace_smoke.py` launches different save/reopen
processes (PIDs 423223/423334), uses API frame hooks and verifies rendered tab
order/active tab and the recovered train row selection. Save 15/reopen 26 frames;
original train/test bytes and zero implicit ML pass. The test source remains
usable while the train source needs relinking; relinking retains train sort,
seed 17/bins 7 and test seed 29/bins 13. The
[restored native tabs/selection](evidence/phase9/session-workspace.png) were
visually inspected. This smoke does not claim the upcoming menu/CLI/layout gate.
Native tab regression passes 197 frames; legacy workspace smoke passes 31/44.

The tab-lifecycle benchmark rerun passes the original budgets with the new
weak bindings/session owner: [report](evidence/phase9/tab-lifecycle-session.json),
445 frames, previews 118.9/126.5 ms, maximum cycle preview 161.3 ms, frame p95
11.57 ms, peak RSS 459.25 MiB, retained growth -5.86 MiB, maximum close 0.219 ms,
two shared workers, zero outstanding jobs/retained closed sessions/worker threads
after exit. Source bytes and temporary cleanup pass; the fixture and limits are
those declared in Step 3, not an arbitrary dataset capacity guarantee.

Commands retain the earlier offline/cache/Mesa settings. Focused tests:
`tests/test_editor_workspaces.py tests/test_session_workspaces.py
 tests/test_editor_sessions.py tests/test_file_sessions.py tests/test_opening.py
 tests/test_workspace_restore.py`; Pyrefly/Ruff/diff; new native
`session_workspace_smoke.py`, existing `editor_tabs_smoke.py`/`workspace_smoke.py`
and `benchmark_editor_tabs.py`. M9.3 remains open until menu/CLI/recent actions,
visible per-source recovery and layout restoration use these session APIs and
pass fresh-process/full-suite acceptance.


## Step 9 / M9.3 exit — Session menus, recovery and saved docking

Normal menu, recent-workspace and CLI startup actions now use whole-session
recipes. The application-owned workspace dialog stays open across restoration;
failed source tabs expose their own replacement/changed-content controls without
routing retry through a plain import that would discard their history. Adjusted
views and selection recovery produce visible messages. Global session jobs and
source-specific recovery guard edits/exports while sibling files remain usable.

Saved native docking and panel visibility take precedence on restore. A fast
restore exposed a startup race: Hello ImGui had already queued its default layout
reset when the saved ini was loaded. Restoration now clears that queued reset.
The strengthened native assertion compares the restored Table dock to the dock
recorded by the separate save process, including when Schema is an inactive tab.

Verification on 2026-10-06:

- **534 full-suite tests passed in 18.08s**; **53 focused tests passed in 1.29s**
  across session/editor/recent/preference/workspace GUI state. New changed-source
  coverage verifies explicit acceptance, retained sorting, cleared selection,
  visible unavailable-column adjustment and an unchanged sibling revision.
- Pyrefly zero errors; Ruff lint/format and diff whitespace checks pass.
- Fresh-process `session_workspace_smoke.py` passes save **15** / restore **45**
  frames (PIDs 429120/429262), through the same initial-workspace route as CLI.
  Native relink-button input restores a moved source while another tab stays
  usable. Saved dock ID 1 and hidden Analysis restore, order/active tab, independent
  seeds/bins/history/selection, source bytes and zero implicit ML all pass.
  [Restored recovery/layout screenshot](evidence/phase9/session-recovery-layout.png)
  was visually inspected: Table is tabbed with Schema at the left and Analysis
  is hidden. Synthetic ImGui input is used; physical mouse input is not claimed.
- Native menu smoke passes **285** frames; legacy workspace migration/relink
  **31/46**; recent sources **16/83**; preferences default/save/reopen **15/21/68**;
  Welcome/multi-open **126**; editor switch/reorder/close/New **193**. Preferences
  also verifies reset/restore, plot defaults, themes and source preservation.
- The Step 8 lifecycle/resource report remains valid; no new worker pool or
  retained payload cache was added in this integration step.

Commands use the cache/offline/Mesa settings above: full `pytest`, focused session
and editor tests, Pyrefly/Ruff/diff checks, `session_workspace_smoke.py`,
`editor_menu_smoke.py`, `workspace_smoke.py`, `recent_smoke.py`,
`preferences_smoke.py`, `welcome_smoke.py` and `editor_tabs_smoke.py`.
M9.3 passes. Its coherent steps are `1d4c576` (storage/migration), `8017e50`
(worker capture/restore/recovery), and the menu/layout acceptance commit
accompanying this section. M9.4 is the next outstanding gate.


## Step 10 / M9.4 foundation — Exact source-bound comparisons

A typed comparison worker prepares explicitly mapped columns from at least two
files. Numeric inputs share Float64 bin edges, account for every finite value,
and expose Count or independently normalized density with original-unit numeric
statistics. Extreme ranges use a common displayed scale and explain it.
Categorical inputs share pooled-frequency order with deterministic ties, keep
nulls distinct from literal text, and aggregate remaining categories into Other.
Counts are exact over each current table; proportions include nulls in the file’s
row denominator. Physical category families must be compatible; numeric/category,
text/identifier/temporal, unavailable columns and no-finite-value inputs produce
clear diagnostics. No automatic feature coercion is added.

Each series carries file ID, table-view ID, dataset revision and column. Shared
bounded workers prepare only changed comparisons; unaffected prepared objects
remain usable. Removing a comparison or closing/changing a contributor abandons
obsolete futures. On-demand bin selection scans only the selected source in a
worker and returns at most its first 10,000 matching source IDs with total count
and first display position. It retains no whole-table selection cache and cannot
publish into a closed or changed source.

Verification on 2026-10-06: **29 focused tests passed in 0.64s** (17 new comparison
fixtures plus 12 session recipe fixtures). Coverage includes unequal-size
known distributions and density integrals, count scales, independent names,
null/nonfinite accounting, empty files, constant/extreme/tiny ranges, exact counts
above the former profile sampling cap, common category order/tail/missing-literal
distinctions, sorted row identity and selection limits, incompatible types,
worker-only computation, only-affected invalidation, executing stale preparation
and closed-source selection. Pyrefly zero errors; Ruff lint/format and diff checks
pass. This foundation adds no GUI behavior; native comparison and resource gates
remain open for the next step. Commands use the earlier cache/offline settings:
`pytest tests/test_cross_file_comparisons.py tests/test_comparison_jobs.py
 tests/test_session_workspaces.py`, Pyrefly/Ruff and diff checks.


## Step 11 / M9.4 exit — Dockable cross-file profiles and session acceptance

Compare files is an application-owned dockable panel beside Explore, available
through View. Users create independent comparisons, map one column per file,
set labels/colors and common bins/category limits, choose Count or Density /
proportion, and apply with Update comparison. Preparation uses the existing
shared pool; only small prepared arrays, metadata and summaries render in frames.
Unapplied edits are marked. Update also retries a busy-worker failure. Numeric
histograms render an explicit step-shaped fill/outline, with a native per-source
legend; categories render common-order horizontal grouped bars. A scrollable
adjacent statistics table uses the same labels/colors.

A selected source and bin/category request worker-prepared row selection. The
editor activates that file, jumps to its first match and updates only its
revision-bound selection, reporting the full count and 10,000-row selection cap.
Closure removes its mappings so the remaining session can still be saved.
Restore prepares basic comparisons from saved mappings but never starts ML.
Numeric category overrides retain nonfinite quality counts and collapse signed
zero consistently for counting/selection. Equal numeric row IDs across files
remain independent.

Verification on 2026-10-06, Linux/Python 3.14.7/Mesa software OpenGL:

- **21 focused tests passed in 0.70s** for comparisons/jobs/editor integration;
  **555 full-suite tests passed in 16.29s**. Added integration covers native-facing
  selection routing after sorting, sibling selection preservation, save/reopen,
  source/revision changes, closure and valid remaining-session save. Added
  failure fixtures cover saturated-worker retry and numeric categorical roles
  with signed zeros, nulls, NaN and infinity, plus exact Decimal categories
  (Polars cannot apply is_finite directly to Decimal). The foundation fixtures remain
  passing. Batch Pyrefly zero errors; Ruff lint/format and diff checks pass.
- Fresh-process `session_comparison_smoke.py` passes native Update and selection
  button input, explicit mismatched columns, labels/colors, shared numeric bins,
  unequal 4/2-row files, common category counts/tail, incompatible-role diagnostics,
  saved mappings/scales and independent selections. Save **92** / restore **105**
  frames (PIDs 441000/441112); **85/93** rendered comparison frames. Configuration
  and floating-panel placement use frame hooks; buttons use synthetic ImGui
  mouse position/delta/events. Source bytes match; implicit ML runs are zero.
- [Numeric overlay](evidence/phase9/comparison-numeric.png) and
  [categorical comparison](evidence/phase9/comparison-categories.png) were visually
  inspected. The numeric fixtures have equal normalized shapes, so the overlays
  coincide despite unequal raw counts. Visual QA caught an invisible stairs fill;
  the explicit shaded outline fixes it. Category counts and adjacent colored
  statistics are visible. Original `comparison_smoke.py` remains a separate
  one-file renderer regression, not replaced by the new cross-file script.
- `benchmark_comparisons.py` declares budgets before running: <=2 s selected
  preparation, <=33 ms frame p95, <=1 GiB peak RSS, <=96 MiB retained growth after
  warmup and <=4 workers. Fixtures are two Parquet files of **100,000/60,000 rows**,
  four columns each (one differently named/scaled numeric feature, one 40-value
  category and two supporting columns), two comparisons and 20 bin/category-limit/
  normalization updates. [Recorded report](evidence/phase9/comparison-resources.json):
  **103 frames / 31 visible comparison frames**; initial preparation **35.08 ms**,
  maximum **46.97 ms**; frame p95 **12.99 ms**; peak RSS **436.61 MiB**; retained
  growth **-19.89 MiB**; three workers; zero outstanding jobs/retained closed tabs.
  Zero worker threads after exit. Source bytes match; **386,460 fixture bytes**
  and the temporary directory are removed. No payload/temp-array cache or spill
  files are added. Cleanup waits until the closing frame releases its active-file
  local reference. These are fixture-specific results, not arbitrary capacity
  or accelerated-rendering claims.
- Native regressions with the new panel pass: session recovery/layout **15/45**
  (saved dock/hidden Analysis verified in different processes), preferences
  default/save/restore **15/21/67**, tabs **194**, editor menus **285**, Welcome
  **126**; legacy workspace **31/46** and recent sources **16/83**. The original
  comparison renderer passes **131** frames / all five modes / error recovery
  after its fixture explicitly selects the current Column Colors source.

Commands use the existing offline/cache/Mesa settings: focused
`pytest tests/test_cross_file_comparisons.py tests/test_comparison_jobs.py
 tests/test_editor_comparisons.py`, full `pytest`, Pyrefly/Ruff/diff;
`session_comparison_smoke.py`, `benchmark_comparisons.py`, original
`comparison_smoke.py`, `session_workspace_smoke.py`, `preferences_smoke.py`,
`editor_tabs_smoke.py`, `editor_menu_smoke.py`, `welcome_smoke.py`,
`workspace_smoke.py` and `recent_smoke.py`.

The 343-line editor coordinator was reviewed at the repository’s 300-line review
trigger: it owns application ordering/opening/publication and borrows separate
job, persistence, file and GUI subsystems. Comparison computation and rendering
are cohesive subpackages; no table-wide work was moved into that coordinator.
No dependencies or lockfile changes are needed for Phase 9.

M9.4 and Phase 9 pass. The comparison steps are `f4ff952` (typed preparation/
identity/jobs) and the GUI/session/native/resource acceptance commit accompanying
this section. Completed session steps remain separate coherent commits. Phase 10
interpretations/previews and every later multimodal gate remain open; existing
unfinished Titanic usability gates retain their previous status.
