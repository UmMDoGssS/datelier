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
| D | Structured/array/checkpoint source and multimodal record/profile families | In progress; source/Inspect, text/image/audio profiles and annotation workflows restored; remaining forms and integration pending |
| E | Comparison families, remaining features and integrated acceptance | In progress; all four comparison families restored; remaining features and integrated acceptance pending |

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

## Fresh Stage D6 — Annotation sources, profiles and overlays

Annotation controllers own explicit VOC/YOLO/COCO/local-manifest association and
profile commands, independent source drafts, row pins, scoped links and lifecycle.
Context reuses typed fields and searchable selectors for target/key fields,
multiple sources/classes, score filters and visible-box limits. Inspect composes
Sources/Associations/Profiles with complete virtual outcome/issue/box tables and
Classes/Sizes/Quality/Boxes subtabs. Size plots use the same persisted viewport.
Polars and immutable sequence tables now share an abstract virtual-table family;
selector labels retain stable identities when different sources have equal names.

Overlay filtering, geometry and conservative label occupancy run on shared
workers. Latest-only scenes retain bounded pickable boxes and reuse idle results.
Identical strokes are combined without removing original boxes, linked picking,
counts or provenance; the selected stroke draws last. Selected-box facts remain
visible during preparation, preventing annotation tabs moving while scrolling.
Closing releases prepared table bindings and scene ownership.

Verification: production/scoped caller Pyrefly zero errors, 96 focused annotation/
image/selection/restore tests, full Ruff lint/format and whitespace checks pass.
All four adapters, confirmed mapping restoration with zero implicit label/pixel
reads, file/view isolation, stale/closed links and bounded row selections pass.
Native explicit association/profiles, picking, cached idle scenes, label avoidance,
subtabs and Expand/Restore pass for 6,000 visible/2,000 retained pickable boxes:
191 frames/21.91 ms p95 for coincident boxes and 186 frames/32.08 ms p95 for distinct
boxes. Both preserve source bytes and zero implicit collection/playback commands.
[Coincident report](evidence/gui-overhaul/fresh-annotations.json) and
[distinct report](evidence/gui-overhaul/fresh-annotations-distinct.json).
Image-profile regression passes 129 frames/18.00 ms p95. Comparison families,
advanced plots, remaining import/table/mapping controls and full caller/native/
resource acceptance remain open. These slice checks do not replace the final
three-size/theme and retention-budget gates.

## Fresh Stage E1 — Shared comparison sources and column comparisons

One editor-owned comparison hub provides immutable file/named-view catalogs,
independent recipe drafts and scoped row-selection ports. Related controllers
share a recipe lifecycle contract. A page-owned comparison composition is shared
across file tabs; file containers borrow its rendering without owning its lifetime.
Columns restores explicit Apply, common numeric/category bins, counts/density,
custom labels/colors, native legends, complete statistics, linked original rows
and persisted comparison/source/bin/viewport choices. Worker completion preserves
focus; clicking a source link navigates immediately and later publishes only rows.

The common file/view and field selectors retain independent drafts. Closing
contributors prunes current and dormant modality recipes before saving. Named-view
Undo/Redo/export commands now target the current view; export labels use the
captured dataset source. Source guards include pending imports. Explicit writes
remain centrally polled after their originating view closes, and closed dialogs
release their captured bindings. Concrete Group composition replaces direct
abstract-container construction, tab routing follows native file/view scope and
route teardown releases inactive children.

Verification: production/scoped caller Pyrefly zero errors, 68 focused comparison/
workspace/multimodal/export tests, full Ruff lint/format and whitespace checks pass.
Tests exercise unapplied drafts, named-view provenance, closed contributors,
restored source/bin/height, stable rows, export ownership and no completion focus
steal. Native source-picker bulk, explicit numeric/category Apply, Expand/Restore,
file activation/draft retention and histogram row links pass in 124 frames,
21.05 ms p95 with source bytes and zero implicit ML/media/corpus work preserved.
[Column report](evidence/gui-overhaul/fresh-column-comparisons.json).
Fresh-process workspace save/restore passes 23/31 frames; text corpus/training
and audio spectrum/listening regressions pass 94/133 frames. Human hearing remains
deferred. Full-project Pyrefly still reports 378 obsolete GUI test/script caller
errors; production and migrated callers are clean. Full caller migration and
whole-milestone acceptance stay open. Text/image/audio comparison reconstruction,
advanced plots, remaining import/table/mapping controls and final resource/native
size/theme gates remain pending.

## Fresh Stage E2 — Shared-tokenizer text comparisons

The text family now uses the comparison recipe/contributor hierarchy, reusable
text-scope/tokenization fields and shared row-link commands. Preparation is explicit
and central polling owns publication. Native charts provide common length bins,
counts/density, full token/document frequency tables, exact corpus/length statistics,
record outcomes, input digests, native legends and shared Auto/Expand/Restore/drag
viewports. The active file/view tokenizer can be copied into the common recipe;
training and artifact configuration remain explicit in Profiles. Named List[Text]
views retain element statistics and original source-row links. Session recipes and
source/bin/tab/frequency/height settings restore idle without saved fitted results.
Draft edits preserve earlier prepared results; contributor revisions, scopes and
closure invalidate them. Selection completion never changes focus.

Verification: production and migrated caller Pyrefly has zero errors; 66 focused
text/comparison/session/restore tests pass. Full Ruff lint/format (679 files) and
whitespace checks pass. Native contributor bulk selection, copied tokenizer,
explicit Prepare, all four subtabs, both chart Expand/Restore and sorted original
row links pass in 184 frames/18.27 ms p95 with source bytes preserved and no implicit
training or per-file corpus preparation.
[Text comparison report](evidence/gui-overhaul/fresh-text-comparisons.json).
Shared column controls regress at 124 frames/20.23 ms p95; corpus/training controls
regress at 94 frames/11.18 ms p95. Image/audio comparisons, advanced plots,
remaining import/table/mapping controls, full old caller migration and final
integrated resource/size/theme gates remain open.

## Fresh Stage E3 — Scoped image comparisons

Image comparisons now compose the shared recipe/contributor/row-link hierarchy
and a reusable scalar histogram component. Per-source record scopes and exact or
seeded pixel samples reuse the image profile form. Dimensions use common original
physical bins; color curves keep mode/dtype/channel families separate. Native
legends, counts/proportions, full scalar statistics and record outcomes are rebuilt.
Both chart tabs support shared Auto/Expand/Restore/drag sizing. Explicit record
links open the originating file or named array view in Inspect, retaining sorted
source-row identity, original pixels and aligned supporting fields. Recipes and
view settings restore idle; source changes and closure invalidate results without
rerunning preparation. No per-file profile or playback starts implicitly.

Verification: production/migrated caller Pyrefly zero errors, 58 focused image/
comparison/session/restore tests, full Ruff lint/format (687 files) and whitespace
checks pass. Native shared source bulk, sampled Prepare, dimension/color/statistics/
record tabs, both chart Expand/Restore, sorted row links and original-pixel record
opening pass in 197 frames/23.86 ms p95 with source bytes preserved.
[Image comparison report](evidence/gui-overhaul/fresh-image-comparisons.json).
The shared single-source image profile form regresses at 129 frames/20.02 ms p95.
Audio comparisons, advanced plots, remaining import/table/mapping controls, full
old caller migration and integrated resource/size/theme acceptance remain open.

## Fresh Stage E4 — Explicit audio comparisons

Audio comparisons reuse the common contributor, recipe, row-link, virtual table
and histogram components. Source eligibility for image/audio references and
confirmed array payloads shares a metadata-only catalog helper. Related comparison
controllers now expose a common polling/closure contract, and the hub traverses
that registry. The last placeholder comparison renderer is removed. Audio scopes,
header/exact signal level, array rate and original-unit thresholds share one form
with per-file Profiles. Distributions retain compatible metric/unit/channel
families, counts/proportions, native legends and shared viewport sizing. Complete
record/channel tables retain original rates, amplitudes, rails and provenance.
Record links activate the originating file/view and open header-first Inspect;
signal preparation and listening remain explicit. Restore/recovery remains idle.
Abandonment feedback states that executing work cannot publish obsolete results.

Verification: production/migrated caller Pyrefly zero errors, 52 focused audio/
comparison/workspace/restore tests, full Ruff lint/format (694 files) and whitespace
checks pass. Native shared contributor bulk, explicit exact signal Prepare,
metric/channel views, distribution/statistics/record tabs, Expand/Restore, sorted
row links and original-rate header opening pass in 155 frames/21.33 ms p95. Source
bytes are preserved and zero output devices are opened.
[Audio comparison report](evidence/gui-overhaul/fresh-audio-comparisons.json).
PSD/mel, header profiles and explicit Play/Pause/Stop regress at 133 frames/
14.51 ms p95 with injected output closed. Actual human hearing remains deferred.
All four comparison families are rebuilt; advanced relationship plots, remaining
import/table/mapping controls, full old caller migration and final integrated
resource/size/theme acceptance remain open.

## Fresh Stage E5 — Categorical relationship families

Relationships now routes scatter and category content through direct child
composition. Related category components share an abstract chart/input lifecycle;
grouped counts and mean/median/sum bars use the bar implementation, while box and
violin subclasses share distribution geometry and row links. Typed contextual
selectors expose eligible categories, groups and numeric values; changing the
category avoids selecting it as its own group. Role changes fall back to an
available view. Native legends, bounded category/Other groups, exclusions, sampling
notes, linked original rows and shared viewport controls remain visible. Category
and scatter heights persist independently. Count bars explicitly navigate to
Profiles. Numeric aggregate recipes retain their representation on restore;
legacy counts open Profiles only when Relationships was the saved view, preserving
saved Inspect focus. Data labels containing native ID separators are escaped.

Verification: production/migrated caller Pyrefly zero errors, 38 focused category/
exploration/workspace/comparison tests, full Ruff lint/format (698 files) and
whitespace checks pass. Native grouped bars, all three aggregates, box/violin row
links after sorting, Expand/Restore and count-to-Profile navigation pass in
126 frames/16.64 ms p95 with source bytes and zero implicit analysis preserved.
[Category report](evidence/gui-overhaul/fresh-categories.json).
3D scatter/camera, pair-grid/diagonal modes, remaining plot/axis/color styles,
import/table/mapping controls, full old caller migration and final integrated
resource/size/theme acceptance remain open.

## Fresh Stage E6 — Scatter dimensions, cameras and coordinate sources

Scatter now composes independent 2D/3D canvas and input components, a common
summary/selection control and explicit camera-face fields. The 3D native input
preserves projected source-row picking, depth tie handling, Ctrl toggles and
Shift-drag visible brushing. Both scatter dimensions use the shared viewport,
retain independent heights and stable native IDs across Expand/Restore, and
provide continuous color scales and native legend visibility. Raw coordinate
selectors are contextual; embedding sources and clustering colors remain explicit
independent choices. Opening a fitted result selects its actual dimension.
Switching to an unavailable/stale coordinate source clears earlier prepared
coordinates; stale cluster colors likewise cannot enter the current dashboard.
Restoring the saved scatter dimension never fits an algorithm.

Verification: production/migrated caller Pyrefly zero errors; 99 focused scatter/
category/controller/analysis tests, full Ruff lint/format (703 files) and whitespace
checks pass. Native 2D/3D picks after sorting, keyboard camera-face selection,
projected Shift brushing, continuous colors and Expand/Restore pass in 119 frames/
16.02 ms p95 with source bytes and zero implicit analysis preserved.
[Scatter report](evidence/gui-overhaul/fresh-scatter.json).
Categorical interactions regress at 126 frames/17.22 ms p95. Explicit analysis
Run/Open result and focus preservation regress at 220 frames/14.58 ms p95.
Full-project Pyrefly still reports 369 obsolete GUI test/script caller errors;
production and migrated callers are clean. Pair-grid/diagonal views, remaining
axis/plot styling, import/table/mapping controls, full caller migration and final
integrated resource/size/theme acceptance remain open.

## Fresh Stage E7 — Correlation pair grids and shared diagonals

Correlations now routes heatmap and bounded, scrollable pair-grid content through
the shared viewport. Each cell owns its prepared distribution or scatter-input
child. Histogram, KDE, ECDF, Box and Violin diagonals reuse the same distribution
series components as Profiles. Sampling, finite-value coverage and fallback facts
remain visible; gesture instructions live in hover help. Grid picks preserve
source-row identity after sorting. Diagonal links select Profiles; pair links
explicitly choose raw 2D axes, clearing an unavailable embedding or 3D route.
An empty feature selection remains empty. Mode, diagonal and height restoration
does not fit an algorithm.

Verification: production/migrated caller Pyrefly zero errors; 21 focused prepared
relationships/scatter/profile and restoration tests pass. Full Ruff lint/format
(709 files) and whitespace checks pass. Native keyboard matrix selection, all
five diagonals, original-row picking, Expand/Restore and profile/pair links pass
in 146 frames/14.64 ms p95 with unchanged source bytes and zero implicit ML.
[Pair-grid report](evidence/gui-overhaul/fresh-pairs.json).
The native numeric-profile resize/navigation regression passes in 64 frames/
13.57 ms p95. Axis controls, import/table/mapping controls, old caller migration
and final integrated resource/size/theme acceptance remain open.

## Fresh Stage E8 — Shared numeric axes and scoped fields

Numeric Profiles, count plots, 2D scatter, category plots and column comparisons
inherit the shared axis-enabled plot family. A GUI-free axis model validates
both drafts before publication, applies ranges once and observes native pan/zoom.
Its controls expose Linear, Symmetric log and Log 10 only on numeric axes;
category coordinates retain their native labels. Fit discards pending ranges;
Expand/Restore keeps the same native plot and axes. New prepared sources reset
old range/scale drafts. Related field types now inherit a common native-ID scope
based on the component path, fixing repeated X/Y and parameter field collisions.

Profiles, pair diagonals and category violins reuse density bandwidth/seed
controls with the domain's valid 0.1–5 range. Numeric lists retain exclusive
selection while exposing numeric distribution controls; count controls appear
only for countable values. Original/scaled units, curve sampling, bounded
outliers and unavailable-density facts remain visible.

Verification: production/migrated caller Pyrefly zero errors; 41 focused axis,
list/profile, restoration, scatter and relationship tests pass. Full Ruff
lint/format (715 files) and whitespace checks pass. Native keyboard range and
Log 10 edits, free zoom after Apply, Fit, invalid-range rejection, category-axis
protection and Expand/Restore pass in 415 frames/14.23 ms p95.
[Axis report](evidence/gui-overhaul/fresh-axes.json).
Profile sizing, scatter and column comparison regressions pass at 64/121/124
frames with 13.96/17.69/29.04 ms p95. Pair/category and explicit analysis regress
at 144/125/228 frames with 16.73/17.54/14.71 ms p95. Source bytes and explicit
analysis behavior pass. Import/table/mapping controls, full old caller migration
and final integrated resource/size/theme acceptance remain open.

## Fresh Stage E9 — Typed source import families and failed reload drafts

Source import settings now compose a common form parent, format-specific children
and the shared typed fields. CSV/TSV, JSON/JSONL, Parquet, XML, media/text, object,
array and checkpoint drafts have separate application models. Literal names/null
tokens and hidden object/array/media recipe fields survive unchanged edits;
media manifest refresh is explicit. Forms validate before requesting workers.
Automatic default JSON opening retains the non-record hierarchy fallback.
Failed reloads keep the usable table, source title, row identities and pipeline;
successful imports replace the pipeline and close obsolete named views. Recovery
must resolve the saved source before importing through these controls.

Session v3 gains an optional import-settings draft alongside the loaded recipe.
It restores failed reload settings without requesting that failed source or
discarding the usable recipe. Old files default to no extra draft. Drafts remain
independent across tabs, format switching and table edits. Saved import settings
must be valid option recipes; invalid draft validation is reported when saving.
Closed import controllers release their bound file callback.

Verification: production/migrated caller Pyrefly zero errors; 79 rebuilt
controller/session/axis/loading checks and 130 import-adapter/family checks pass
(with overlap). Full Ruff lint/format (729 files) and whitespace checks pass.
Native delimiter/null-token typing, invalid submission, failure preservation,
successful retry and ten format forms pass in 291 frames/13.06 ms p95.
[Import report](evidence/gui-overhaul/fresh-imports.json).
Separate-process session save/restore regress in 23/31 frames with
14.15/10.77 ms p95. Object/array/checkpoint navigation regresses in 168 frames/
18.70 ms p95; basic sizing/navigation regresses in 64 frames/13.97 ms p95.
Source bytes and zero implicit analysis/playback/collection work pass. Remaining
table/reference/mapping controls, old caller migration and final integrated
resource/size/theme acceptance remain open.

## Fresh Stage E10 — Prepared table cells and shared reference previews

The virtual table now composes prepared headers, source rows and styled
text/reference cells. Physical types, interpretations, null/distinct counts and
inference evidence are available without frame-time preparation. Numeric shading
supports percentile, linear and validated custom ranges; categorical colors,
null/nonfinite/out-of-range markers, badges and whole-row selection return.
Native column identities stay stable when badges change. Array payload aliases
remain distinct from filesystem references.

Table and gallery reference renderers inherit a common preview family and borrow
one file-owned texture cache. Pre-frame preparation owns invalidation, upload
budget and teardown. Gallery images/text stay bounded, including fixed card
spacing for short previews. Reference roots, filters, cache sizes, explicit
retry/abandon and literal value mappings use shared fields/selectors. Ambiguity
choosers virtualize candidates and retain their source revision; stale choices
cannot map another row. Mapping never rewrites original cells. Styles, thumbnails
and reference recipes restore independently per file/view.

Verification: production/migrated caller Pyrefly zero errors; 73 rebuilt
controller/session/reference/presentation checks and 11 focused new table/reference
checks pass (with overlap). Full Ruff lint/format (740 files) and whitespace
checks pass. Native mapping, custom shading/badges, sorted original-row selection,
bounded text gallery and fresh-process restoration pass in 177/31 frames with
17.55/12.23 ms p95. Three image assets retain 9,216 GPU bytes under the configured
1 MiB budget; the shared cache uploads at most three per frame (limit four).
[Table report](evidence/gui-overhaul/fresh-table.json).
Original image pixels/text spans/audio waveform regress at 55 frames/23.56 ms
p95. Basic sizing/navigation regresses at 64 frames/13.88 ms p95. Source bytes
and zero implicit collection analysis/playback pass. Advanced mapping/browser
controls, full old caller migration and final integrated resource/size/theme
acceptance remain open.

## Fresh Stage E11 — Numeric slice and supporting-column controllers

NumPy members, mapped records and CPU tensors share a GUI-free slice draft and
explicit prepare command. Metadata validates axes, coordinates, window lengths,
structured fields and display ranges before work starts. Invalid drafts cannot
decode payloads or replace the earlier prepared slice. Per-member drafts survive
navigation; record changes update source coordinates while retaining window and
display drafts. Valid unprepared slice controls persist without decoding.

Record mappings now accept multidimensional supporting arrays, configurable record
axes/fixed coordinates, scalar structured fields and independent column aliases.
The same member can supply multiple fields. Metadata rejects unequal record counts,
duplicate aliases and nonscalar fields without truncation. Supporting forms render
at most eight entries per page; irrelevant field/page controls stay hidden.
Confirmation prepares supporting columns in shared workers and keeps payloads lazy.
Saved mapped views retain the existing explicit preparation/recovery behavior.

Array/tensor vector and matrix plots now inherit the shared numeric axis family;
scalar and nonnumeric previews show their raw values without an empty plot area.
Member labels preserve literal ImGui separator characters and selected metadata
uses cached lookup.

Verification: production/migrated caller Pyrefly zero errors; 109 rebuilt and
array/checkpoint correctness checks pass (three dependency warnings). Eighteen
focused numeric/source/mapping/workspace checks pass after the final form changes.
Full Ruff lint/format (744 files) and whitespace checks pass. Native supporting
axis/alias/coordinate edits, alignment rejection, sorted exact record windows and
expand/restore pass in 263 frames at 20.04 ms p95; source/object/CPU checkpoint
preparation regresses in 164
frames at 19.12 ms p95. Original image/text/audio records regress in 55 frames at
24.09 ms p95. Source bytes and zero implicit analysis/playback pass.
[Numeric report](evidence/gui-overhaul/fresh-numeric.json).
Full-project Pyrefly remains open: the E10 audit reports 368 errors from obsolete
GUI tests/scripts. Browser, remaining preview workflows, old caller migration and
final integrated resource/size/theme acceptance remain open.

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
