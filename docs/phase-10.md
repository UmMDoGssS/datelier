# Phase 10 — Interpretations, previews, and Inspect

Phase 9 is the entry baseline. Phase 10 is being delivered in bounded steps:

1. Import interpretations and exact first-source-column identifier rule.
2. Nearby reference index, explicit mappings, prioritized lazy image/text previews.
3. Typed conditional presentation and saved per-view scales.
4. Direct media/text record collections and shared gallery/detail Inspect.
5. Native restoration, source/revision/lifecycle and measured resource acceptance.

M10.2–M10.4 and the overall phase remain open until their recorded checks pass.
The existing Titanic UX acceptance status is unchanged.

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
