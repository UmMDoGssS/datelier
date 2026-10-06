# Phase 10 — Interpretations, previews, and Inspect

Phase 10 passes M10.1–M10.4 on the Phase 9 baseline, delivered in bounded steps:

1. Import interpretations and exact first-source-column identifier rule.
2. Nearby reference index, explicit mappings, prioritized lazy image/text previews.
3. Typed conditional presentation and saved per-view scales.
4. Direct media/text record collections and shared gallery/detail Inspect.
5. Native restoration, source/revision/lifecycle and measured resource acceptance.

The sections below record step-level checks and final acceptance. Phase 11 is
next. The existing Titanic UX acceptance status is unchanged.

## M10.1 interpretation behavior

Lexical evidence from at most 256 non-null strings recognizes image/audio/text
extensions and local path syntax without accessing the filesystem. Prose has
priority over identifiers. At import, a nonempty first source column with fully
unique, non-null integer/string values becomes Identifier when recognizable
reference/text evidence does not win. Floats, empty, duplicate and null-containing
first columns do not satisfy that rule. Named unique IDs elsewhere remain
recognized. Interpretation evidence and physical dtype remain distinct.

Same-type row edits retain imported interpretations, so filtering a category down
to unique values cannot create an identifier. Type changes infer a compatible
role without reapplying the first-source-column import heuristic. Overrides use
the existing replayable operations and undo/redo; profiles, colors and automatic
ML feature controls exclude references/IDs/text unless explicitly reinterpreted.
No source cells or row identities are rewritten and no payload is loaded.

Verification on Python 3.14.7/Linux uses
`UV_CACHE_DIR=/tmp/datelier-uv uv run --no-sync` with the existing locked environment.
Focused interpretation, roles, comparisons, exploration, profiles, scatter,
selection, transforms and workspace controls: **67 passed**. Pyrefly reports
zero errors; Ruff lint/format and diff whitespace pass. The native Mesa Schema
smoke (`LIBGL_ALWAYS_SOFTWARE=1 POLARS_MAX_THREADS=8 ... python
scripts/column_roles_smoke.py`) passes **61 frames**, real override/undo,
identifier feature exclusion, unchanged Titanic bytes and zero implicit ML runs.
The GUI requires access to the local display outside the filesystem sandbox.
Historical numeric-chart fixtures now use explicitly floating first features;
new fixtures directly cover the authorized integer/string ID rule.

M10.1 passes. The milestone full suite reports **568 passed**.

## M10.2 dependency and scheduling foundation

Pillow **12.3.0** is added by `uv add pillow`, with the lockfile updated by uv.
The Linux/Python 3.14 probe decodes a 400×200 RGB PNG in a worker into a contiguous
128×64 RGBA thumbnail; **30 native Mesa frames / six texture uploads** render it
and release owning handles before backend teardown. The installed ImGui Bundle
`TextureGpu` API owns and releases textures on the GUI thread. Pillow's
[image API](https://pillow.readthedocs.io/en/stable/reference/Image.html) documents
lazy open and thumbnail behavior; this probe is Datelier's dependency evidence.

The shared bounded scheduler accepts priority: visible/selected preparation
precedes queued discovery, FIFO within equal priorities; executing work continues
until completion or cooperative abandonment. Cancellation removes queued closures
and releases capacity. Owners still close independently. Nine focused scheduling,
file-session and editor-session tests pass; Pyrefly, Ruff lint/format and whitespace
checks pass. This foundation does not yet pass M10.2's feature/resource gates.

## Nearby references and lazy preparation backend

Discovery scans the dataset directory then its parent's subtree (editable roots),
with extension filters, cooperative stop/progress and directory diagnostics.
Symlink directories are not traversed; file aliases retain their names while
canonical targets are deduplicated. Exact absolute/dataset-relative paths win,
then indexed filenames, then stems. Multiple targets require a column/value
mapping; mapped missing files never fall back to another target.

Visible jobs prepare worker-only 128-pixel image thumbnails, first-frame metadata,
UTF-8 excerpts limited to 4096 bytes with truncation labels, or stat metadata for
other references. Fingerprints include canonical path/size/mtime; changed-during-
decode results have diagnostics. File/revision/configuration switches drop pending
publication, while unchanged assets can reuse CPU data across revisions. Indexing
runs below visible-job priority. CPU retention is byte-bounded (default 16 MiB),
with bounded request/result counts; evicted previews can be decoded again.
Retry clears failed previews; closing cooperatively abandons indexing and safely
abandons executing decodes rather than claiming they stopped immediately.

Nine focused reference/scheduling tests pass, including duplicate extensions,
exact/relative/stem mappings, symlinks/loops, roots/filters, corrupt/missing/changed
assets, lazy publication, source/revision cache invalidation and eviction/reload.
Pyrefly and Ruff lint/format/whitespace pass. Native integration, persisted controls
and resource acceptance remain the next M10.2 step.

## M10.2 table controls and native/resource acceptance

Visible reference cells request prepared thumbnails/excerpts through file-owned
jobs. Table geometry stays virtualized; image rows have a fixed 64-pixel height.
Hover exposes the original value, canonical target, metadata/excerpt or diagnostic.
Ambiguous/missing cells offer a native popup with explicit candidates or an exact
file field. Settings expose roots, filters, retry/abandon and CPU/GPU budgets.
Workspaces and preferences save reference recipes and thumbnail visibility; legacy
recipes restore defaults. No payload or texture enters a workspace. Headless
session save/restore verifies mappings/settings with no decoded data or ML.

GUI-thread GPU retention defaults to 8 MiB with at most four uploads/frame.
Textures used in the current draw remain pinned until the next frame. Invalidation
is deferred, and before-exit/GUI callback-error guards release all owning handles
while the backend is still live. Closed files release both caches. Removed
reference interpretations abandon pending publication and clear retained resources.

Native Mesa evidence: `reference_previews_smoke.py` passes **27 frames**, scroll,
explicit ambiguity mapping, independent same-source tabs, switching/reuse and
zero retained CPU/GPU bytes on closure; frame p95 **11.34 ms**. The real mouse
ambiguity popup smoke (`reference_mapping_smoke.py`) selects the intended red
image rather than the other same-name target, and captures its table thumbnail.
Visual review checks prepared image rows, original labels, missing-reference
recovery, and usable surrounding controls.

`benchmark_references.py` declares budgets before execution: metadata <=2 s,
index <=5 s, first thumbnail <=2 s, frame p95 <=33 ms, peak RSS <=768 MiB,
post-warmup growth <=32 MiB, four shared workers, configured CPU/GPU retention
<=2/1 MiB. Fixture: **100,000 rows / four columns**, **1,000 256×128 RGB PNGs**,
20 large virtual scroll jumps. [Measured report](evidence/phase10/reference-resources.json):
metadata **118.42 ms**, index **158.99 ms**, first thumbnail **196.46 ms**;
**323 frames**, p95 **14.50 ms**, peak RSS **392.05 MiB**, retained growth
**-27.17 MiB**, CPU/GPU each **196,608 bytes**, four workers. Closed sessions,
outstanding jobs and worker threads after exit are all zero. Original source
bytes match; **648,851 fixture bytes** and temporary files are removed.
These are fixture-specific Linux software-OpenGL results.

Focused preview/session persistence checks: **17 passed**. Milestone full suite:
**575 passed**; Pyrefly zero errors, Ruff lint/format and diff whitespace pass.
M10.2 passes. Conditional styles and shared Inspect remain open.

## M10.3 typed presentation foundation

Worker-prepared preview cells carry typed null, numeric/nonfinite and stable
category metadata independently of their truncated strings. Numeric ranges use
exact finite min/max and 2nd/98th percentile endpoints, computed during worker
inspection preparation. Percentile shading clips to that interval and marks
values below/above it; linear min/max and finite custom ranges are available.
Constants use a neutral midpoint; nonfinite values have a separate marker.
Scaled arithmetic avoids overflow for ±1e308. Category hashes use original typed
values and a bounded palette, stable after sorting/filtering and across processes;
colors are cues rather than unique encodings of every high-cardinality value.

46 focused presentation/preview/transform/import tests pass; Pyrefly zero errors,
Ruff lint/format and whitespace pass. Tests cover typed NULL vs literal NULL,
nonfinite/constant values, percentile/custom extremes, large magnitudes, stable
category colors and sorted/filtered row identity. GUI/persistence and M10.3
acceptance are the next slice.

## M10.3 native styles and resource acceptance

The table now applies typed conditional backgrounds and interpretation badges.
Per-view controls expose colors, badges, percentile/linear/custom scales and
validated custom endpoints. Selected rows retain their linked-selection color
rather than being obscured by cell shading. Theme-aware alpha keeps original
values readable. Readable text markers (`<`, `>`, `=`, `(null)`, `!`) replace glyphs
that visual review found absent in the bundled font. Literal `NULL` remains an
ordinary value. High-cardinality colors deliberately reuse a bounded palette.

`table_styles_smoke.py --theme dark/light`: **38 frames each**, actual mouse row
selection, all three scales, sorted source-ID alignment, undo and visible
null/literal-NULL/nonfinite/category cells. Both final screenshots were visually
reviewed. Workspace round trips retain custom scale/endpoints and badges;
legacy views gain defaults. Focused presentation/preview/workspace/preferences
checks: **27 passed**, with **12 affected checks rerun** after readable markers.

The existing `inspection_smoke.py` now targets the measured visible-row pixel for
wheel input and waits for reload completion before jumping; the old fixed pixel
was outside the shortened table, and fixed-frame actions could precede wide-table
reload completion. Assertions remain real native wheel, aligned last-page IDs,
bounded rendering and nonblocking reload.

[Million-row report](evidence/phase10/table-million.json): **1,000,000 × 8**,
180 frames; startup **309.49 ms**, live reload **342.06 ms**, frame p95 **15.09 ms**,
wheel-to-prepared **37.41 ms**, peak RSS **774.11 MiB**, at most **five rendered
rows**. [Wide report](evidence/phase10/table-wide.json): **100,000 × 66**, 220 frames;
startup **1,005.11 ms**, reload **703.88 ms**, p95 **19.05 ms**, wheel **32.31 ms**,
peak RSS **710.64 MiB**, five rendered rows, column window 48. Both preserve
<=33 ms frame p95 and <=1 GiB fixture RSS; no table-wide calculation enters frames.
These are existing CSV fixture/resource directions, not capacity guarantees.

Pyrefly, Ruff lint/format and diff whitespace pass. M10.3 passes with its full-suite
check; direct sources and shared Inspect remain open.

M10.3 final full suite: **578 passed** after the marker/readability changes.

## M10.4 direct record source foundation

Media/text extensions open through the existing worker loader. Files become one
metadata record (path/member/kind/size); even a corrupt image opens its metadata
before lazy decoding reports an error. Text file-versus-line mode is explicit;
line mode retains original Unicode content and physical 1-based line provenance,
including empty lines. Invalid UTF-8 line imports fail transactionally.

Open Folder lists supported tabular and media files and adds a native **Open
folder as media collection** action. Recursive manifests are sorted relative
member paths, without traversing symlink directories. Saved options retain member
order and original text-line counts. Missing/shorter members create placeholder
records, keeping other source-record IDs stable. Refreshing import membership is
explicit. Directory source fingerprints hash supported member names, sizes and
mtimes, without reading every media payload; metadata changes require normal
changed-source acceptance/relink. This detects metadata changes rather than
content edits that deliberately preserve size and mtime. Ordinary file workspace
fingerprints still hash source bytes. No manifest bundles payloads.

Direct record paths bypass unnecessary nearby indexing; lazy visible previews
use the existing shared bounded workers/caches. Empty collections remain usable.
58 focused media/opening/tabular-import/workspace/control checks pass. The real
native folder action and independent two-line import pass **38 frames**, two
collection metadata records and zero implicit ML. Pyrefly and Ruff lint/format/
whitespace pass. Shared gallery/detail Inspect and final M10.4 acceptance remain
open.

## Shared Inspect preparation foundation

Record collections prepare current display positions and stable source-row IDs
in workers. Ranges refer to current row positions; linked selection filters only
IDs present in the active revision; seeded sampling draws from sorted source IDs
so sorting does not change the chosen records. Four-record pages prepare any
chosen primary/supporting columns, including all 41 fields in a deterministic wide
fixture. Primary values truncate explicitly at 4096 characters; supporting values
at 256. The GUI will virtualize both record and field lists.

File-owned jobs key collections by revision, settings and originating selection,
clear obsolete pages and retain at most four prepared pages/two pending requests.
Gallery/focus changes do not rebuild identities. Twelve focused record/selection/
media checks pass, including range/filter/sort alignment, deterministic samples,
wide supporting columns, superseded file revisions and controlled closure during
executing preparation without late publication. Pyrefly and Ruff lint/format/
whitespace pass. No GUI integration or M10.4 completion is claimed yet.

## M10.4 gallery/detail and phase acceptance

The dockable **Inspect** panel offers virtual gallery cards and focused Previous/
Next navigation. Primary fields prefer references, then text; direct media opening
focuses Inspect, while workspace restoration respects its saved layout. Row ranges,
linked selections and seeded random samples retain file/revision/source-row identity.
Supporting fields use a searchable virtual checklist with All/Clear/Done and a
virtual field list, without the table page's 16-column restriction. Selecting a
card links to its source row/table position. Focused and gallery text show prepared
excerpts, and missing/corrupt references show actionable diagnostics inline.

Per-file settings save mode, range/count/seed, primary/supporting fields, gallery/
focus and panel scroll alongside reference settings and conditional presentation.
Global defaults retain cache/display choices but do not apply another source's
roots or exact mappings. Explicit source reloads invalidate CPU/GPU payloads even
when the path/stat metadata matches; same-dataset edits and tab switching can
reuse unchanged assets. View restoration also invalidates GPU presentation safely.
Custom numeric values outside tiny ranges clamp before normalization, avoiding
underflow; `=` describes a flat display scale rather than asserting every source
value is constant.

Known fixed media manifests/line counts retain saved selections during changed-
source recovery; missing or shorter members keep placeholders and the same source
IDs. Generic changed tabular sources keep their existing selection reset behavior.
Relinked line files preserve original line slots even when renamed. Refreshing the
manifest remains explicit and makes current membership available. Plain relative
paths such as `sub/a.bin` also receive lexical local-path interpretation.

Native `inspect_smoke.py`: **94 frames**, real mouse All-fields choice (**42
fields**), popup Done, Focus and Next; sorted/source sample alignment and independent
cross-file selections verified. Final gallery screenshot reviewed for source-row
labels, image preview, supporting values and bounded cards. Direct source regression
passes **33 frames** with a native folder action and explicit text-line records.

`phase10_workspace_smoke.py` runs three separate processes: save **21 frames**,
restore **6**, changed-member recovery **7**. Three tabs restore (media folder,
line text, CSV), replayed sort/role override, selected ID 2, exact mappings/cache
sizes, custom style, focused primary/supporting fields, docking and hidden Analysis.
Other tabs stay usable while the changed folder awaits recovery. After explicit
acceptance, missing `2.png` stays selected with its original ID, null size and visible
missing-reference diagnostic. No implicit ML runs, source bytes preserved except
the deliberately removed fixture, and the temporary directory is removed.
[Fresh-process report](evidence/phase10/workspace-restoration.json).

The `benchmark_references.py --inspect` extension declares the existing reference
budgets plus <=2 s initial record and sample-update latency, and fewer than eight
rendered gallery cards. Fixture: **100,000 rows / four columns / 1,000 images**,
20 scroll jumps and 20 explicit **10,000-record seeded samples**. The
[Inspect resource report](evidence/phase10/inspect-resources.json) passes:
metadata **130.39 ms**, index **172.31 ms**, first image **210.94 ms**;
first record **156.67 ms**, maximum sample update **152.83 ms**;
**323 frames**, p95 **12.18 ms**, peak RSS **387.62 MiB**, retained growth
**-18.61 MiB**, CPU/GPU each **819,200 bytes** (limits 2/1 MiB), four workers,
**at most two rendered cards across the run**. Closed sessions, outstanding jobs
and post-exit workers are zero; source bytes and temporary cleanup pass. These extend the already-passed
million-row/wide-table gates rather than promise arbitrary collection capacity.

Dependency clean probe: `uv run --no-project --isolated --with pillow==12.3.0
--python .venv/bin/python ...` installs a fresh isolated Pillow environment and
successfully decodes/resizes PNG on Python 3.14. The offline attempt lacked needed
registry metadata; the authorized network retry succeeds. The locked project is
consistent (`uv lock --check --offline`). Existing runtime dependencies are
unchanged apart from Pillow.

The 304-line app bootstrap was reviewed at the 300-line trigger: it retains runner,
panel bindings and resource-safe callback teardown; file ownership, record jobs,
controls and rendering remain separate cohesive subsystems. No ML/media computation
or filesystem discovery was moved into frame callbacks. Full modality statistics,
original-resolution image tools, tokenization and audio playback remain their
later authorized phases. Linux Mesa software rendering is verified; accelerated
rendering and other platforms remain unverified.

Final source-preservation review added shared worker-side destination checks:
exports/workspace writes cannot overwrite media-folder members, symlink targets
or hardlinks, while separate CSV metadata and workspace files remain usable.
Deterministic export/save/restore tests verify unchanged asset bytes. Restoring
unavailable Inspect fields against an already bound schema selects an available
primary field and preserves valid supporting choices, gallery and seed settings;
an explicit empty supporting list stays empty.

Final verification: **593 tests passed** (`uv run --no-sync pytest -q`), Pyrefly
**zero errors** (one existing suppression), Ruff lint and format (**306 files**),
and diff whitespace pass. The final native direct-source, gallery/detail and
three-process restoration regressions pass after the preservation changes.
M10.4 and Phase 10 pass. Phase 11–14 implementation/dependency gates and the
previously unfinished Titanic usability gates retain their open status.
