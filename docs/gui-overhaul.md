# GUI architecture and workflow overhaul

Authorized on 2026-10-10 after code exploration and user decisions. Production
GUI baseline: 122 Python modules, 15,543 lines, 62 classes and 110 module-level
functions, with no shared component inheritance. This is an architecture and
workflow change, not a data-engine rewrite. Existing capability evidence remains
valid; the outstanding Titanic usability gates and deferred audio listening
check retain their status.

## Decisions and acceptance contract

Use classes for views and reusable widgets, with abstract component families and
immediate-child rendering. Pure formatting, drawing and geometry helpers may
remain functions. Constructor injection supplies narrow prepared state and
commands; leaf components must not receive whole file/editor sessions.
Application controllers coordinate jobs, selections, navigation and persistence.
Keep source/view/revision identity, shared workers, lazy media loading and GUI
thread texture ownership. Background completion must not steal navigation focus.

The final shell has four dockable panels: source/columns, canvas, context and
table. Central tabs are Profiles, Relationships, Correlations, Inspect and Compare
files; comparison subtabs are Columns, Text, Images and Audio. Context holds View,
Transform and History. Remove standalone Analysis after relocating every unique
setting/result, including cluster centers/inertia and provenance. Export becomes
a File-menu dialog. Switching file tabs returns to that file's last inspection
view and preserves comparison drafts. All modalities have equal acceptance
weight. Keep existing themes, Unicode fonts and dependencies.

Column pickers share search, role groups, virtualization and bulk actions, but
retain independent selections, ordering and domain eligibility/limits. Viewport
components share resize/Auto/Expand/Restore while preserving content-specific
zoom, axes/cameras, selection, pixel readouts and token spans. Keep gallery cards
bounded. Move gesture help out of normal content; retain data facts, errors,
sampling, exclusions and truncation. Recipes/settings survive migration; old
docking/hidden-panel state resets with a notice. Planned formats: session v3,
preferences v2, layout v2, with legacy single-source/v2 session readers.

## Fresh rebuild, superseding incremental migration

On 2026-10-10 the user explicitly requested replacing the production GUI folder
and rebuilding features from the ground up, accepting non-runnable early commits
and obsolete GUI tests. The incremental migration below is historical evidence,
not acceptance of the replacement. Its committed state is preserved on
`codex/gui-overhaul-saved-c22e0be`; unfinished media extraction is preserved in the
stash named `gui overhaul before fresh rebuild 2026-10-10`. A temporary reference
copy is available at `/tmp/datelier-rebuild-reference` during development.

Retain domain engines, pure application models, font assets and selected stateless
native helpers. Rebuild composition, controllers, bindings and feature renderers.
Do not retain the former FileSession/EditorSession or production compatibility
wrappers. Every leaf receives feature-specific state and commands. All rendering
components implement Component.render; container classes render direct children.

| Stage | Delivery | Status |
| --- | --- | --- |
| A | Replace GUI package; GUI-free file/record/editor runtime and component contracts | Complete; desktop deliberately not runnable |
| B | Shared controls, shell, columns, table, tabular profiles and plots | Complete; basic inspection shell runnable |
| C | Contextual analysis, transforms/history, export and workspace/preferences | Complete; advanced plot modes tracked separately |
| D | Structured/array/checkpoint source and multimodal record/profile families | In progress; source/Inspect and text/image/audio profiles restored; annotations pending |
| E | Comparison families, remaining features and integrated acceptance | Pending |

Each stage runs scoped Pyrefly, behavioral tests, full Ruff checks and diff review
before commit. Full Pyrefly/old GUI tests remain open while their imports target
removed modules. Native gates begin when the replacement shell is runnable.
This is the user's explicit exception to the usual runnable-step workflow; do
not mark unperformed gates passed. Final acceptance still requires all capabilities,
full suite migration, native input at three sizes/themes, resource budgets,
source/row identity and restoration/lifecycle verification.

Stage A verification: scoped Pyrefly has zero errors; 17 runtime/loading/editing/
worker tests pass. Source bytes, sorted row identity, independent files, no implicit
analysis/text profile/playback, close isolation and repeated close pass. Full Ruff
lint/format and diff checks pass. Full Pyrefly reports 297 errors from obsolete
GUI callers; this gate stays open. CLI desktop launch and old GUI tests are knowingly
unavailable until Stage B and test migration. No native rendering is claimed.

## Fresh Stage B — Runnable inspection shell

The replacement shell composes four free-docking panels with a context drawer
below 1100 px. Shared searchable/grouped/virtualized column pickers, typed fields,
facts tables and Auto/Expand/Fit/resize viewports form the control foundation.
Numeric Histogram/KDE/ECDF/Box/Violin implementations share an abstract family;
profile routing dispatches by prepared kind. Column interpretations, virtualized
source-ID table rows, bounded 2D scatter with linked input and correlation heatmap
render from injected feature controllers. Assembly alone receives file/editor
controllers. The CLI desktop entry point is restored.

Verification: scoped Pyrefly zero errors, 20 focused controller/selection/schema/
profile/distribution checks, full Ruff lint/format and diff checks pass. Native
runs at 1280×800 and 1024×768 pass pointer resize and tab navigation, source hashes
and zero implicit analysis/playback. The 1280 run takes 64 frames, 13.91 ms p95.
[1280 report](evidence/gui-overhaul/fresh-shell-1280.json) and
[compact report](evidence/gui-overhaul/fresh-shell-1024.json) retain raw evidence;
captures are beside them. This is basic shell acceptance only. Contextual analysis,
advanced plots, file browser, transformations, persistence, specialized content
and comparison renderers are still pending. Full old GUI caller migration remains
open. Historical incremental evidence below does not certify replacement features.

## Fresh Stage C1 — Analysis and reversible commands

Relationships context now owns feature/preprocessing/seed inputs, every existing
algorithm editor, explicit Run/Cancel/Open result, stale/draft indicators, full
provenance and cluster counts/centers/inertia. Embedding plots are prepared by the
application runtime. Completion preserves navigation; Open result chooses the
coordinate/color source. Related operation forms share selectors and typed fields
for Sort/Filter/Keep columns/Cast/Fill/Drop/Lookup/Derived column. History shows
applied/undone recipes. Compare disables its Transform/History actions. Export is
a source-labelled File dialog, captured independently of later tab activation;
worker-side destination guards now also protect other open source files/aliases.

Verification: scoped Pyrefly zero errors, 79 focused runtime/analysis/edit/export
checks, full Ruff lint/format and diff checks pass. Native feature-picker bulk,
explicit PCA, navigation during fitting, no completion focus theft and explicit
Open result pass in 219 frames, 15.02 ms p95 with unchanged source bytes.
[Analysis report](evidence/gui-overhaul/fresh-analysis.json). Persistence, structured
and multimodal content, advanced plots and comparisons remain open.

## Fresh Stage C2 — Controller-owned sessions, browsing and preferences

Whole-session snapshot/installation, recovery, recent sources and background
preference I/O are GUI-free. Named record views are independent application
controllers sharing their owning source metadata and bounded services. Capture
preserves replayable operations, selections, independent settings, named views,
failed import drafts and all comparison recipes. Worker-only fingerprinting and
partial source recovery retain usable files. Viewport heights are model-bound.
The File menu now owns browser/workspace/export dialogs and recent opening; themes
use a shared action family. Rebuild layouts are identified separately from obsolete
native trees; old recipes/settings survive a brief, dismissible layout notice.
Assembly and shell lifetime have separate modules.

Verification: scoped Pyrefly zero errors, 80 focused controller/session/restore/
preference checks, full Ruff lint/format and diff checks pass. Fresh native save
(23 frames, 13.30 ms p95) and separate-process restore (31 frames, 10.53 ms p95)
preserve Compare/History, viewport sizes, selection, sorted IDs and docking; source
bytes and zero implicit fitting/playback pass. The native tab container now keeps
first-frame defaults from overwriting restored routes. Shared resize/navigation
regression passes 64 frames, 14.13 ms p95. [Workspace report](evidence/gui-overhaul/fresh-workspace.json).
Native file-browser selection, remaining advanced plots and all specialized
content/comparison acceptance remain open, as does full old caller migration.

## Fresh Stage D1 — Shared record Inspect

Inspect now composes virtualized collection/card/header/content/supporting-field
components. Focused text, image, audio, nested and scalar content share typed
record routing and model-bound viewports; gallery previews stay bounded. Original
image pixels retain lazy metadata/window preparation, exact Unicode/token offsets
and full text paging are restored, and audio headers remain decode-free until
an explicit waveform/profile command. Context shows only controls applicable to
that record family. Page teardown releases textures on the GUI thread, including
callback failures. Closing views releases their prepared record bindings.

Verification: scoped Pyrefly zero errors, 26 focused controller/record/image/audio/
text tests, full Ruff lint/format and diff checks pass. Migrated text/record tests
exercise new controller APIs, including restored missing-field recovery and
line-text defaults. Native original pixels, NFC source spans and explicit waveform
input pass with unchanged source bytes and zero implicit collection work/playback.
[Record report](evidence/gui-overhaul/fresh-records.json) retains timing evidence.
Structured sources, array content, media profiles/training/annotations/playback,
comparison families and advanced plots remain open.

## Fresh Stage D2 — Structured and numeric source families

Object and numeric source browsers share an abstract prepared-state contract.
Virtual object listings navigate every node, page complete scalar text and open
independent typed record views. Array/tensor listings reuse one bounded slice
editor and scalar/vector/matrix display family, with exact raw cells, display-only
colors/ranges, complex/structured fields and original tensor storage bits.
Confirmed array mappings share the column picker for aligned supporting members;
generic record payloads use a separate scoped slice job and stable source row IDs.
The source browser remains with its owner while column metadata follows the active
record view. Semantic slice drafts, member/record mode, cache limits and viewport
sizes restore without decoding. Duplicate pending record openings are coalesced.
Assembly now separates source/Inspect composition from tabular composition.

Verification: scoped Pyrefly zero errors, 93 focused object/array/checkpoint/record/
restore checks pass (three existing PyTorch warnings), full Ruff lint/format and
diff checks pass. Migrated old behavioral tests exposed and fixed shutdown
cancellation of queued storage cleanup. Native member selection, explicit NumPy
and CPU checkpoint slices, object record extraction, original values/row IDs,
unchanged sources and zero implicit collection work/playback pass in 167 frames,
17.81 ms p95. [Source report](evidence/gui-overhaul/fresh-sources.json). Focused media
Inspect regression passes 55 frames, 22.37 ms p95. Advanced mapping forms, media
profiles/training/annotations/playback, comparisons, plots and full caller/native/
resource acceptance remain open.

## Fresh Stage D3 — Text profile and tokenizer workflow

Related column/text profile implementations now inherit a profile-content family;
prepared role routing chooses their immediate child. Text corpus and record jobs
have independent ownership while sharing the saved tokenizer recipe. Exact corpus
statistics, document/element lengths, complete virtual frequency/outcome tables,
resizable distribution/frequency plots and persisted subtabs return to Profiles.
Explicit scope, local artifact import, BPE/Unigram training forms, progress,
cancellation, digests and provenance stay contextual. Completion preserves focus.
Inspect supports text-list elements and independent original/token-piece paging.
Clearing a profile selection persists across frames and restoration.

Verification: whole production package Pyrefly zero errors (one existing suppression,
35 warnings); scoped new callers also pass. Forty focused corpus/training/Unicode/
list-text/record/restore checks pass. Full Ruff lint/format and diff checks pass.
Native exact profiling, profile subtabs and selected-corpus training/provenance pass
in 94 frames, 16.03 ms p95, with unchanged source and no implicit playback.
[Text profile report](evidence/gui-overhaul/fresh-text-profiles.json). Focused media
Inspect regression passes 55 frames, 20.12 ms p95. Full project Pyrefly/pytest still
await obsolete caller migration. Media profiles/annotations/spectral/playback,
comparisons, advanced plots and integrated native/resource acceptance remain open.

## Fresh Stage D4 — Original audio and listening

Audio record content composes metadata, explicit sample/signal/profile commands,
related waveform/spectral chart classes, exact raw/channel tables, provenance and
listening controls. Shared viewport sizing covers waveform, PSD and HTK mel views;
worker-colored tiles upload and release on the GUI thread. Original frame/time,
FFT/hop/window/frequency, display/range, thresholds and cache controls remain
contextual. Playback supports explicit output discovery, Play/Pause/Resume/Stop,
volume, selected channel/range and seek, with an injected output factory. Switching
file or named view releases the matching stream. Audio collection headers/exact
statistics have independent explicit job ownership and saved recipes.

Media forms now share an abstract typed parent and live in a cohesive package;
typed settings bindings reduce repeated getter/setter construction. Mapped payload
Inspect retains original row identity after the visible record-index column is
removed, while ordinary supporting fields can be inspected independently.
Cancellation feedback describes abandonment instead of claiming execution stopped.

Verification: whole production package Pyrefly zero errors (one existing suppression,
36 warnings); scoped callers pass. Eighty-six focused audio/playback/source/text/
record/restore checks, full Ruff lint/format and diff checks pass. Native PSD/mel,
header collection and deterministic injected Play/Pause/Stop pass in 133 frames,
16.80 ms p95; original-rate output samples, source bytes and device closure pass.
[Audio report](evidence/gui-overhaul/fresh-audio.json). Shared media record regression
passes 55 frames, 23.08 ms p95. Human listening remains deferred; this step does not
claim actual hearing. Image/annotation profiles and controls, comparisons, advanced
plots, full caller migration and integrated acceptance remain open.

## Fresh Stage D5 — Image profiles and display controls

Explicit image collection profiles compose shared Statistics/Dimensions/Colors/
Record outcomes subtabs, prepared histograms and model-bound resizable viewports.
Exact and seeded pixel scopes retain provenance and original-value statistics.
Outcome rows open source-aligned focused Inspect through a reusable guarded record
command. Mapped image payloads survive sorting and removal of display identity
columns; supporting scalar fields remain ordinary values. Image context restores
channel, fixed numeric heatmap coordinates, validated display-range drafts and
CPU/GPU/temporary cache controls. Worker publication remains in central polling.

Verification: production/scoped caller Pyrefly zero errors, 65 focused image/
profile/record/restore tests, full Ruff lint/format and whitespace checks pass.
Migrated workspace tests retain independent fields, heights, selection and no
implicit collection decoding. Native sampled profiling, all image subtabs,
Expand/Restore, outcome opening, display-range input and exact original pixels
pass in 129 frames, 18.40 ms p95, preserving sources and zero implicit playback.
The native workflow exposed and fixed child-command navigation being overwritten
by the containing tab row. [Image report](evidence/gui-overhaul/fresh-image-profiles.json).
Annotation adapters/associations/overlays, comparison families, advanced plots,
remaining import/table controls and full caller/native/resource acceptance remain
open. Historical baseline evidence does not certify those replacement features.

## Baseline evidence

Before implementation, 38 targeted editor/session/schema-role/profile-selection/
axis tests passed. The existing two-file benchmark passed 30 open/close cycles
with 100,000 rows and eight numeric columns per file: 12.48 ms frame p95,
494.69 MiB peak RSS, 189.13 ms maximum cycle preview and 0.33 ms maximum close.
Four workers, zero outstanding jobs/retained closed sessions and unchanged source
bytes pass. [Raw report](evidence/gui-overhaul/baseline-tabs.json) preserves the
original budgets: 33 ms frame p95/close, 2 s preview, 1 GiB peak RSS, 96 MiB
retained growth and at most four workers.

GUI checks require desktop display access: the sandbox cannot connect to :0.
The benchmark was rerun successfully with reviewed desktop access and Linux
Mesa software OpenGL. Use `LIBGL_ALWAYS_SOFTWARE=1 POLARS_MAX_THREADS=8
UV_CACHE_DIR=/tmp/datelier-uv-cache uv run --offline` for native commands.
Representative prior captures remain in the existing modality evidence folders;
fresh redesigned-shell visual/input acceptance has not yet run.

## Step 1 — Component and schema pilot

Committed as `cf48004`.

`Component`, `Container`, `Panel` and `FrameContext` define the first rendering
contract. The schema panel delegates to summary/table components, and the table
renders visible row components. `SchemaController` prepares immutable column
metadata once per revision, receives only an edit-command dependency and rejects
stale, unavailable, busy or failed role changes. Native rendering no longer reads
the dataset or prepares role metadata.

`GuiProbe` records targets by file/view/revision/component path and releases them
at each frame boundary. `run_gui` gains an additive `on_probe_frame` hook;
existing hooks remain usable during migration. `component_schema_smoke.py` uses
that hook to exercise native role selection and undo without accessing widget
internals. Current panel labels/layout and workspace formats remain unchanged.
Native keyboard navigation is now enabled. The original app enabled docking
only, so popup keyboard selection was unavailable. The preview smoke explicitly
reveals the schema dock tab instead of requiring a hidden tab to have rendered.

Verification on 2026-10-10:

- Batch Pyrefly: zero errors (one existing suppression).
- Schema/probe and existing editor/workspace/role/profile/axis tests: **41 passed**.
- Ruff lint, format and diff whitespace checks pass.
- Native component input: **48 frames**, **13.03 ms p95**; mouse opens the combo,
  keyboard selects Numeric, undo restores the inferred ID role. Source bytes,
  values and source row IDs are preserved; zero implicit ML runs.
- Native 10,000-row/eight-column preview: **180 frames**, **133.64 ms** first
  preview, **32.93 ms p95**, at most six rendered rows. Background reload, schema
  docking, end-of-table row identity and wheel scrolling pass. Pixel capture was
  visually reviewed for schema labels, role controls and bounded table rendering.

[Component input report](evidence/gui-overhaul/schema-component.json),
[preview report](evidence/gui-overhaul/schema-preview.json) and
[preview capture](evidence/gui-overhaul/schema-preview.png) retain the evidence.
Native input is synthetic ImGui input, not human pointer timing. The redesigned
shell, all-family sizing and whole-milestone regressions remain outstanding.

Commands, using the environments above:

```sh
uv run --offline pyrefly check
uv run --offline pytest tests/test_schema_controller.py tests/test_gui_probe.py tests/test_editor_sessions.py tests/test_workspace_gui_state.py tests/test_column_roles.py tests/test_profile_selection.py tests/test_axis_controls.py
uv run --offline ruff check .
uv run --offline ruff format --check .
uv run --offline scripts/component_schema_smoke.py
uv run --offline scripts/inspection_smoke.py --output /tmp/datelier-component-preview.ppm
```

## Step 2a — Dataset runtime publication and ownership

`DatasetRuntime` owns import/edit/workspace publication, preview/exploration/export
polling and the lifetime of those services, independently of GUI imports. It
returns typed source changes to the presentation coordinator, which retains
view-specific configuration/reset work during migration. Existing file-session
service fields temporarily borrow the same instances; no second data authority,
extra worker pool or service-locator mechanism is introduced.

The runtime publishes inspection, preview revision and linked-selection revision
together. Restore installs the replayed pipeline before requesting exploration;
closed runtimes cannot publish late import results. Close is idempotent and
preserves sibling services using the shared pool. Probe scopes now use stable
owning-file and record-view identities, rather than a mutable record-view name.

Verification on 2026-10-10:

- Pyrefly: zero errors; Ruff lint/format and diff whitespace checks pass.
- Runtime/loading/edit/workspace/editor/shared-worker/multimodal focused tests:
  **37 passed**. New headless tests cover reversible sorted row identity,
  unchanged source bytes, restored pipelines, sibling isolation, idempotent close
  and an executing import completing after close.
- Full pytest suite: **1,060 passed** in 31.43 s, with three dependency warnings.
- Native component override/undo regression passes after runtime extraction.
- Multi-file resources: **460 frames**, **13.74 ms p95**, **499.94 MiB** peak RSS,
  **203.77 ms** maximum cycle preview and **0.36 ms** maximum close across 30
  cycles. Four workers, zero retained closed sessions/outstanding jobs/remaining
  worker threads, unchanged source bytes and temporary-directory cleanup pass.
- Native whole-session save (**15 frames**) and a separate-process restore
  (**45 frames**) preserve tab order and run no implicit ML.

[Runtime resource report](evidence/gui-overhaul/runtime-tabs.json) and
[fresh-process workspace report](evidence/gui-overhaul/runtime-workspace.json)
retain the evidence. Application-wide coordination and specialized controllers
are still pending within Step 2. This slice does not claim completion of the
redesigned shell or any other pending delivery step.

Additional commands:

```sh
uv run --offline pytest tests/test_dataset_runtime.py tests/test_loading.py tests/test_editing.py tests/test_workspace_restore.py tests/test_editor_sessions.py tests/test_shared_jobs.py tests/test_multimodal_sessions.py
uv run --offline pytest
uv run --offline scripts/benchmark_editor_tabs.py
uv run --offline scripts/session_workspace_smoke.py
```

## Step 2b — Analysis and plot state separation

Analysis drafts/request construction, plot drafts/schema binding and analysis
worker/result coordination now live in GUI-free application modules. Native
analysis configuration is an `AnalysisForm` component with a typed injected
binding. State consumers/tests import application settings directly; workspace
recipe identifiers and behavior remain unchanged. The GUI analysis session and
plot controls retain presentation methods over those models during migration.

Verification: zero Pyrefly errors, 32 focused role/workspace/analysis/scatter/file
checks, Ruff lint/format and whitespace checks pass. Native analysis workbench
passes 271 frames: explicit PCA, k-means colors in raw/embedding space, linked
embedding selection and unchanged source bytes. Application-wide coordination
and specialized media controllers remain pending; this is a verified subdivision
of Step 2, not whole-overhaul acceptance.

## Step 3a — Shared column selection and algorithm editors

The shared searchable, grouped, virtualized column picker now serves Profiles,
analysis inputs, correlations, raw axes/colors, categorical relationships, Inspect
primary/supporting fields and transformation columns. Injected selection policies
preserve bounded feature sets, insertion/catalog order, exclusive nonnumeric
profiles and single-field selection. Transformation column selection no longer
requires hand-written JSON. Concrete algorithm parameter editors share an abstract
parent and registry rather than a central algorithm `if/elif` renderer.

Verification: Pyrefly zero errors, 45 focused behavior checks, Ruff lint/format
and whitespace checks pass. Native profile selection exercises numeric comparison,
exclusive categories, every plot mode and fresh-process saved selection (324
frames; source preserved, zero implicit ML). Native explicit PCA/k-means, linked
selection and raw/embedding colors pass (271 frames). Shared viewports and remaining
specialized selector migrations are pending within Step 3.

## Step 3b — Shared content viewport and contextual help

`ResizableViewport` owns content height, drag divider, Auto, Expand/Restore and
stable native IDs. `PlotArea` supplies axes/camera controls over that component.
Focused image inspection, original text/token tables and cross-file column charts
now share the viewport; image zoom/pan and token offsets retain their own models.
Gallery cards remain bounded. Gesture-only scatter Details is removed; contextual
help replaces movement instructions in plots, image caches, table selection and
annotation overlays. Statistical and source facts stay visible.

Verification: Pyrefly zero errors, 59 focused axis/image/record/workspace checks,
Ruff lint/format and whitespace checks pass. Native shared drag/expand/restore
passes 40 frames. Image native pixel/fit/zoom/pan/channels passes 212 frames and
fresh-process restoration 80 frames (p95 12.89/12.58 ms). Text passes 97 frames,
fresh-process restore 31 frames, complete EOF, exact original accent span [2,4)
and sorting/support-field alignment. Sources are preserved.

The historical plot-area smoke had an ID-inferred synthetic x column and an
offscreen divider in the cramped old dock layout. The fixture is corrected; its
integrated sizing/input gate stays open until the redesigned shell is verified.
The independent shared viewport input gate passes. New media viewport heights
still need the scheduled persistence migration.

## Step 4a — Exploration tab and parameter field families

Explore renders registered `ExploreTab` subclasses for Profiles, Relationships,
Correlations and Inspect. The former page-level tab switch is removed; each tab
owns its content rendering. Profile content receives only its default text field
and media presentation commands rather than the complete file session. Trusted
parameter fields dispatch through Boolean/Integer/Float/Choice editor subclasses.
Pending correlation preparation preserves saved pair-grid mode and numeric defaults.

Verification: Pyrefly zero errors; 33 focused workspace/scatter/analysis/profile
checks (27 rerun after fixing pending correlation behavior), Ruff lint/format and
whitespace checks pass. Native explicit PCA/k-means/colors/selection passes 270
frames; native DBSCAN parameters, explicit Run, no implicit fit and linked 3D
pass 173 frames. Contextual analysis relocation and multimodal leaf bindings are
still pending within the tab hierarchy work.

## Steps 4b / 7a — Contextual analysis and four-panel shell

The page now composes Source/Columns, Canvas, Context and Table panels. Canvas
contains the four inspection tabs and Compare files with Columns/Text/Images/Audio
subtabs. Context has View/Transform/History; profile and record selectors and
relationship/correlation settings live there. Analysis settings/results/provenance,
cluster counts/centers/inertia remain accessible in Relationships context. The
standalone Analysis, transform/history, comparison, schema and export windows are
removed. Export is a source-bound File dialog; Undo/Redo, Context and Table toggles
are available beside file tabs. A compact column catalog replaces the cramped
schema table in the left panel.

Worker publication announces a pending result without selecting coordinates or
changing the inspection tab. Open result performs explicit navigation. File
activation exits Compare while keeping drafts and each file's inspection state.
Default widths below 1100 use a context drawer; saved/customized docking is
preserved. Real legacy dock layouts reset with a notice while recipes/settings
remain intact. The broader versioned migration and specialized bindings remain
pending, so this is not the completed overhaul milestone.

Verification: Pyrefly zero errors, Ruff lint/format and whitespace checks pass;
34 focused navigation/workspace/file tests pass (37 earlier including analysis).
Full suite: **1,066 passed**, three dependency warnings, 29.24 s. Native scatter
resize/expand/axes/camera preservation passes at 1280×800 and 1024×768 (128 frames
each). Native schema role/undo passes 48 frames, 14.12 ms p95. Explicit
PCA/k-means and linked colors pass 282 frames. Navigation input passes 162 frames:
no completion focus theft, explicit Open result, file exits Compare, drafts and
source bytes preserved. Image fit/zoom/pan/channel/pixels and fresh-process restore
pass 212/80 frames, 14.00/13.28 ms p95. The initial shell capture was visually
reviewed; final all-theme/all-modality sizing acceptance stays open.

## Step 7b — Versioned navigation and viewport migration

Whole-session workspaces now write v3 with layout v2, canvas/context navigation
and customization state. Preferences write v2/layout v2. Readers accept legacy
single-source recipes, v2 sessions and v1 preferences, preserving source recipes,
operations, analysis settings, selections and media settings while clearing old
docking/hidden panels with a visible notice. Image and original text/token viewport
heights are saved per file/view. Current custom docking/visibility is retained.

Native verification found the dock-window vector property returns copies; live
visibility changes now use `dockable_window_of_name`. This also fixes toolbar
Context/Table toggles and restored hidden panels. Custom docking is observed after
initial builder settlement rather than being overwritten by compact defaults.

Verification: Pyrefly zero errors, 60 focused persistence/GUI-state/media checks,
Ruff lint/format and whitespace checks pass. New tests cover v2 recipe/identity
migration, v1 preference theme/settings preservation, current navigation/content
height round trips and invalid heights. Native separate-process session save (15
frames) and restore/relink (45 frames) retain custom docking, hidden Context, tab
order/history/selections and zero implicit ML. A second separate-process check
retains Compare/History and image/text/token heights, with zero implicit analysis,
playback or tokenizer commands and unchanged source bytes. Whole-milestone
specialized component and all-modality acceptance remains open.
