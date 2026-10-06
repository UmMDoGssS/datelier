# Phase 11 — Structured objects, arrays, and checkpoints

Phase 11 is underway on the verified Phase 10 baseline. Its completion gate
remains open until M11.1–M11.4 and the full restoration/resource acceptance pass.

The bounded delivery sequence is:

1. Typed JSON/TOML sources, preserved object hierarchy and node extraction.
2. Native tree navigation and independently editable named table views with
   whole-session restoration and source/node/record provenance.
3. NPY/NPZ metadata, selected-member temporary storage, mapped slices and plots.
4. Confirmable array record axes/layouts, aligned supporting fields and saved views.
5. Optional CPU PyTorch installation, restricted checkpoint browsing and acceptance.

## Structured source foundation

`ImportFormat.OBJECT` and `ObjectOptions` support explicit JSON object loading
and automatic `.toml` opening. Immutable nodes retain nested arrays/objects,
scalar types and TOML date/time values, with bounded scalar previews. Typed node
paths distinguish string keys from array indices, including punctuation in keys.
Selected arrays of flat scalar objects enter the existing Polars pipeline;
source-row IDs are original record indices within the selected node. TOML
calendar/time fields use lossless ISO text in extracted tables. TOML nonfinite
floats remain nonfinite; invalid JSON constants/overflow, duplicate keys,
malformed sources and unavailable/incompatible nodes fail locally. Empty/scalar
sources remain browsable; empty arrays without a schema cannot be table views.
Mixed scalar types can be read explicitly as text. Legacy flat JSON/JSONL import
behavior remains covered. No source bytes are rewritten.

Node options use the strict workspace recipe codec, and source fingerprint checks
and operation replay apply to extracted tables. This foundation does not yet
provide named view ownership or the native tree; M11.1 remains open.

Verification on Linux/Python 3.14 uses `UV_CACHE_DIR=/tmp/datelier-uv uv run
--no-sync`: focused object/JSON/format/workspace tests **115 passed**; Pyrefly
**zero errors** (one existing suppression); Ruff lint/format (**310 files**) and
diff whitespace pass. Native Mesa smoke: blank workbench **20 frames**, TOML
metadata source **30 frames**. Local display access requires sandbox escalation;
the initial sandboxed GLFW attempt could not open display `:0`, and the authorized
retry passed. Native tree input, named views, full-suite milestone evidence and
all M11.2–M11.4 gates remain outstanding.

## M11.1 native browsing, named views and acceptance

Editor opening keeps compatible flat JSON tables and opens other valid JSON
shapes in the object browser. Explicit flat JSON import settings retain their
legacy validation. The Source browser expands object/array nodes, displays scalar
previews and supports root/parent/focused navigation. Each branch pages 32 children;
at most 128 tree rows render per frame. Object field lookup uses immutable indexes
built in workers; scalar preview truncation precedes string representation. Tree
rendering does not traverse complete large record arrays in frame callbacks.

Selected flat record arrays create named, file-owned table views through the
shared workers. Preparation is transactional: malformed/mixed/nested nodes keep
the current view and report a diagnostic. Each view owns its revision, source-row
IDs, history, controls, selections, inspection and jobs. Reopening an existing
node/text setting focuses its view; table controls switch between the original
source and named views. Source request changes reject pending extraction, and
closure abandons executing work without allowing late publication. Namespaced
views also participate in explicit profile comparisons. GPU teardown covers
all owning file/view sessions while the rendering backend is live.

Whole-session recipes now save named view identities/locators, active view,
selections, independent histories/settings, selected/focused node paths and
expanded branches. Older version-one/two recipes retain default fields. Restored
views share the owning immutable hierarchy, avoiding repeated object parsing.
Missing sources leave unrelated tabs usable; relinking updates owner and child
references together. Changed sources use existing explicit recovery. Workspace
files contain recipes rather than object snapshots. Invalid extraction never
removes another view or rewrites source bytes.

`object_views_smoke.py --output docs/evidence/phase11/object-views.json` runs two
fresh processes under Mesa software OpenGL: save **40 frames**, restore **16**.
Real mouse input selects the records node and opens its table view. Sort history,
source IDs **[1, 0]**, selected ID **1**, named view and object node restore; no ML
runs implicitly. [Report](evidence/phase11/object-views.json) and
[screenshot](evidence/phase11/object-views.png) record the workflow. Visual review
confirms readable tree, original hierarchy, view selector and aligned table.
The existing direct-media/line-source smoke passes **33 frames**; native Schema
role/undo/source-preservation regression passes **63 frames**.

`benchmark_objects.py --output docs/evidence/phase11/object-resources.json` declares
budgets before execution: source open <=5 s, named view <=3 s, frame p95 <=33 ms,
peak RSS <=1 GiB, four shared workers. Fixture: **50,000 records × three fields**,
nested metadata, **180 native frames**. [Measured report](evidence/phase11/object-resources.json):
open **599.14 ms**, extraction **177.02 ms**, frame p95 **11.62 ms**, peak RSS
**458.42 MiB**, four workers; source bytes match and workers/temp files are removed
on closure. These are fixture-specific Linux software-rendering measurements.
JSON/TOML hierarchy storage remains in memory; array payload handling is M11.2.

Final verification: **620 tests passed**, Pyrefly **zero errors** (one existing
suppression), Ruff lint/format (**317 files**) and diff whitespace pass. The full
suite caught an overly broad prepared-source option check that rejected existing
text-line relinking; constraining it to explicitly prepared object sources fixed
the regression, and the final full suite/native workflow were rerun. The 300-line
FileSession and larger editor/bootstrap files were reviewed: ownership and panel
binding stay cohesive while object views/browser and recipe capture are separate.
M11.1 passes. M11.2–M11.4 and the overall Phase 11 gate remain open.

## M11.2 header-only foundation

The array adapter reads NPY versions 1/2/3 and NPZ member headers into typed
metadata: original member name, shape/dtype/order, header size, raw payload size,
stored/container bytes and compression. It does not call `numpy.load` or
materialize payloads. The binary header length is checked before reading it
(default 10,000 bytes, adjustable), then NumPy's public header readers validate
it. Version 3 UTF-8 headers use an equivalent ASCII-escaped literal through the
public v2 validator, retaining Unicode structured field names and the original
header offset. No private reader or type suppression is needed.

Empty archives, scalar/empty/higher-dimensional/string/structured/endian arrays
retain metadata. Corrupt/truncated members have local diagnostics while other
members remain available; duplicate names fail explicitly. Object dtypes remain
visible but payload inspection requires a non-object source, with no pickle
loading. Source metadata changes during inspection reject the catalog.

Reference: [NumPy format specification](https://numpy.org/doc/stable/reference/generated/numpy.lib.format.html)
and [mapped loading](https://numpy.org/doc/stable/reference/generated/numpy.load.html).
Verified against locked NumPy **2.5.3** on Python 3.14/Linux. Focused metadata,
object-source and named-view tests **35 passed**; Pyrefly **zero errors** (one
existing suppression), Ruff lint/format (**322 files**) and diff whitespace pass.
This backend foundation has no GUI changes; temporary member storage, mmap/slice
lifecycle, renderer integration and their native/resource evidence remain the
next M11.2 steps. The M11.2 entry/exit gates remain open.

## Selected-member storage foundation

`ArrayStore` prepares only a requested NPZ member, streams it in 1 MiB chunks to
an owning temporary NPY file, validates metadata/CRC/size and checks source
size/mtime before and after preparation. Both compressed and stored members use
reusable temporary storage; standalone NPY maps its original bytes read-only.
Mapped leases preserve dtype, byte order, Fortran layout, Unicode structured
fields and raw values; empty arrays use a zero-payload read-only array. Each
worker lease closes its mmap base after preparing copied slices; views must not
escape the lease. No source writes or pickle loading occur.

Default disk retention is 256 MiB with least-recently-used eviction of unleased
members. Larger selected members remain available while leased, then are removed;
retention is distinct from a capacity restriction. Abandonment is cooperative
between chunks. Cleanup waits for executing preparation/mapped leases, without
blocking closure on their I/O. Disk-creation failures are retryable, partial files
are removed, and stale source metadata prevents reuse/publication.

Storage/metadata correctness checks **20 passed**, including compressed/stored
reuse, unselected members, oversized eviction/reload, scalar/string/empty/
structured/Fortran/endian values, object-pickle rejection, disk failure/retry,
controlled abandonment during decompression, active-lease closure, and repeated
mmap release. Pyrefly **zero errors** (one existing suppression), Ruff lint/format
(**324 files**) and diff whitespace pass. This worker-only foundation does not
change GUI behavior. Array jobs, visible slice/plot controls, persisted array
locators and native/resource acceptance remain required before M11.2 passes.

## Exact slice preparation foundation

Worker preparation selects one/two display axes, fixes all remaining coordinates
and copies an exact bounded window from a read-only lease. Reversed axis order
transposes the prepared window rather than changing coordinate meaning. Window
starts/counts and truncation are explicit; preparation caps 16,384 cells and aims
at <=8 MiB raw buffers (one oversized element can exceed that target). Raw dtype,
endian order, scalar/string/structured values and nonfinite entries remain intact.
Structured scalar fields and complex magnitude/real/imaginary components can supply
plot values while original records remain available. Subarray/string/non-numeric
fields retain raw cells and an actionable plotting diagnostic.

Numeric float64 plot values and normalized colors are separate read-only display
buffers. Finite range/constant midpoint/nonfinite count are prepared in workers;
scaled normalization handles ±1e308 without overflowing. Empty dimensions create
empty views and scalars retain one exact cell. Backend cells truncate explicitly
at 256 characters. Plot conversion does not mutate raw values.

Slice/storage/metadata checks **35 passed**; Pyrefly **zero errors** (one existing
suppression), Ruff lint/format (**326 files**) and diff whitespace pass. Fixtures
cover n-D axis order/fixed indices, exact shifted windows, endian dtype, scalar/
empty/string/structured/nonfinite/complex/large/constant values and invalid fields,
axes, positions/counts. No GUI changes are included in this foundation. M11.2's
jobs, native controls, saved locators and resource acceptance remain open.

## M11.2 native arrays and acceptance

NPY/NPZ files now open through the normal editor/catalog/loader as metadata tables.
Array member names identify arrays within their source, including path-like names;
they do not trigger nearby-media discovery. The Source browser virtualizes member
selection and exposes vector/matrix axes, fixed coordinates, exact start/count
windows, structured scalar fields and complex components. **Prepare slice** is
explicit. Reopening/restoring reads metadata and saved controls, with no payload
preparation, decompressed cache or implicit ML. Reimported sources reset their
local controls; views in other files stay independent.

File-owned jobs share the bounded scheduler and tag publication by revision and
slice settings. Source/setting switches and closure reject obsolete results;
cooperative abandonment checks between decompression chunks, with visible byte
progress while extracting. Disk retention is editable and saved. Cleanup is
queued on workers and survives owner closure. Cache display properties use
constant-time snapshots, so frames do not wait on file eviction locks.

Prepared vector values use gaps for nonfinite entries. Matrix heatmaps use a
continuous Viridis scale over the selected finite range, with prepared gray spans
for nonfinite cells. Plot indices and raw virtual rows retain original coordinates;
hover shows the full source index tuple. Newly prepared windows fit their own
coordinates; subsequent frames retain pan/zoom. Raw values stay read-only.
ImPlot's binding rejects read-only ndarray inputs, so dedicated numeric/heatmap
presentation buffers are writable; raw/source data remain separate. GUI callbacks
do not read files, decompress members, normalize arrays or scan complete members.

`array_views_smoke.py --output docs/evidence/phase11/array-views.json` passes two
fresh processes: save **78 frames**, restore **35**. Real keyboard input fixes axis
0 to index **1**; a native button prepares the expected **3×4** plane. Additional
explicit vector/nonfinite matrix preparations verify gaps and gray spans, and
returning to the cube reuses its extracted member. Restoration proves metadata-only
opening before another explicit native preparation. [Report](evidence/phase11/array-views.json)
and [reviewed screenshot](evidence/phase11/array-views.png). The final M11.1 native
object regression also passes save/restore **40/16 frames**.

`benchmark_arrays.py --output docs/evidence/phase11/array-resources.json` declares
metadata <=2 s, first selected slice <=3 s, subsequent windows <=1 s, frame p95
<=33 ms, peak RSS <=1 GiB, disk retention <=16 MiB and four workers. Fixture:
compressed **8×512×512 float32** selected data, **1024×1024×32 uint8** unselected
data, **20 exact 128×128 shifted windows**, **152 frames**. The
[resource report](evidence/phase11/array-resources.json) passes: metadata **118.83 ms**,
first slice **65.32 ms**, maximum update **31.13 ms**, frame p95 **29.66 ms**, peak
RSS **381.54 MiB**. One extraction retains **8,388,736 bytes**, exactly the selected
member's NPY storage; the 32 MiB unselected payload is never materialized. Worker
threads and temporary member storage are removed after exit, and source bytes
match. These are Linux Mesa software-rendering fixture measurements.

Final full suite: **659 tests passed**; Pyrefly **zero errors** (one existing
suppression), Ruff lint/format (**333 files**) and diff whitespace pass. Focused
session tests prove metadata-only open/restore, exact explicit preparation,
stale-revision rejection, source/member namespace and cleanup. The larger
FileSession/bootstrap files were reviewed again: array jobs, storage, preparation
and native rendering stay separate; file ownership remains cohesive.
M11.2 passes. Confirmable record mappings (M11.3), optional CPU checkpoints
(M11.4) and the overall Phase 11 completion/restoration gate remain open.

## M11.3 record-mapping foundation

Metadata-only suggestions identify tentative record axes from matching scalar
array lengths, image/channel candidates, numeric matrices and long waveform
axes. Ambiguous axes remain explicit evidence requiring confirmation; suggestions
do not create a table or read payloads. Typed mappings configure record/display/
channel axes, additional fixed coordinates and named supporting arrays/fields.
Length mismatches fail without truncation before reading supporting data.

Explicit record preparation creates a Polars source-index column and scalar
supporting columns; dominant image/array payloads remain referenced and unopened.
Original record-axis positions are source-row IDs. Supporting arrays can use
alternate record axes and fixed coordinates; numeric endian/float16 conversion
is isolated at the Polars boundary and diagnostics retain original dtypes.
Unsupported scalar engine representations use text rather than narrowing complex
or extended-float precision. Source-index interpretation remains Identifier even
for an empty record schema. Per-record slice locators include source index,
layout/display axes and chosen channel, including scalar record previews.

Mapping/slice/storage tests **33 passed**: NHWC, NCHW, alternate record axes,
grayscale/heatmap/waveform/scalar/empty records, aligned supporting coordinates,
axis ambiguity, mismatch diagnostics, original source IDs and label/image alignment
after sort/undo. Pyrefly **zero errors** (one existing suppression), Ruff lint/format
(**336 files**) and diff whitespace pass. This is a backend foundation without
GUI changes. Confirmation/edit controls, file-owned mapped views, linked record
inspection, lazy workspace restoration and full M11.3 acceptance remain open.

Mapped recipes now persist typed layout, axis, coordinate and supporting-column
settings. Whole-session restoration validates source fingerprints and supporting
lengths using metadata alone, preserving the mapping, operation history and
source-row selection until explicit record preparation. Changed sources reset
selection; relinking updates both owner and child references. Preparation then
loads supporting values and replays saved operations. Sources remain protected
from workspace overwrite. Focused mapping/workspace/session/object regression
tests **30 passed**; Pyrefly **zero errors** (one existing suppression), Ruff
lint/format (**338 files**), the full suite (**669 passed**) and diff whitespace
pass. This adds backend recipes;
the native deferred-view and confirmation controls are still pending.

File-owned mapped views now borrow the source's bounded member store while
retaining independent revisions, worker requests, pipelines and selections.
Explicit confirmation loads scalar support only; duplicate mappings focus the
existing view, and mismatches leave it usable. Closing a view abandons its requests
without abandoning the owner's cache. Restored mapped views retain a separate
deferred recipe, can be resaved without payload reads, and prepare/replay only on
an explicit editor command. Session installation is separated from FileSession's
polling/lifetime responsibilities.

Ownership/workspace/array/object tests **14 passed**; sort/filter/undo retain
original pixel alignment, deferred reopen forbids member reads, and child closure
keeps the source cache usable. Pyrefly **zero errors** (one existing suppression),
Ruff lint/format (**340 files**) and diff whitespace pass. The existing native
array save/restore regression passes **78/35 frames**, including native fixed
coordinate entry, preparation, source preservation and temporary cleanup.
Native mapping controls and linked record presentation remain open.

## M11.3 native mappings and acceptance

Source browser now offers **Configure array records**. Worker-prepared header
suggestions remain editable drafts: primary member, record axis, layout,
spatial/sample/channel axes, fixed coordinates, scalar supporting members,
column names and structured fields. Suggestions include up to 16 initial scalar
columns; additional columns can be added explicitly, with paged controls for up
to 256. Ambiguous record axes retain explanatory evidence. **Confirm mapping and
open records** creates a named independent view. Editing and reconfirming another
mapping leaves existing views intact; invalid/mismatched mappings report errors
without truncating or changing the active table.

Mapped Source browser previews follow linked table selections or Inspect's
range/seeded-sample focus using immutable source-row identity. Supporting values
are prepared on workers and displayed in a virtual list beside the original
record index. Numeric image/grayscale planes, heatmaps, scalar values and waveform
windows use the existing exact slice/plot renderer. A separate **Prepare record
payload** command loads the chosen member; image channels remain numeric planes,
with full image tools scheduled in Phase 13. Windows, raw values, finite ranges
and fixed source coordinates remain visible. Loading placeholders reserve space
for navigation/supporting values so controls do not move as workers complete.

Whole-session reopen and legacy single-source migration preserve mappings,
histories, selections and slice locators with headers alone. The Table preview
offers **Prepare saved array records** to load supporting values and replay
operations; payload preparation remains separate. Deferred recipes can be
resaved and relinked without opening members. Child jobs cannot clear or close
the owner's cache. Closed or revised views reject pending results.

`array_records_smoke.py --output docs/evidence/phase11/array-records.json` passes
two fresh native processes: confirmation/save **76 frames**, deferred restore
**47**. Before confirmation there is no table/member storage; confirmation reads
only labels. Native selection after sorting chooses source record **3**, label
**5**, table row **2**, and the matching **5×6** channel plane. Restoration reads
headers only, then native commands explicitly prepare saved scalar records and
the selected payload. [Report](evidence/phase11/array-records.json) and
[reviewed screenshot](evidence/phase11/array-records.png) show the aligned source
record, supporting values, selected table row and spatial heatmap. Frame p95 is
**16.09/14.23 ms** on Linux Mesa; sources and temporary cleanup pass. Native
object save/restore (**40/16 frames**) and array slices (**78/35**) regressions
also pass.

Final full suite **675 passed**. Mapping tests cover NHWC/NCHW, alternate axes,
gray/heatmap/waveform/scalar/empty records, ambiguity, unequal lengths, structured
supporting coordinates, unique editable column names, source-index alignment
through sorting/filtering/undo and seeded Inspect samples. Session tests cover
deferred payload-free reopen/resave, explicit history replay, changed source,
relink/source protection, cache ownership and revision rejection. Pyrefly **zero
errors** (one existing suppression), Ruff lint/format (**345 files**) and diff
whitespace pass. FileSession is **300 lines** after separating installation;
mapping jobs, controls and linked presentation remain cohesive modules.
M11.3 passes. M11.4's optional CPU checkpoint dependency/inspection and the full
Phase 11 completion gate remain open.

## M11.4 optional CPU dependency gate

The `checkpoints` extra adds **torch 2.14.1+cpu** from the explicit official
CPU index; ordinary installations keep the existing dependency set. `uv.lock`
was regenerated by uv and contains no CUDA packages. Use `uv sync --locked
--extra checkpoints` for checkpoint development/inspection. The source/index
configuration follows [uv's PyTorch integration guide](https://docs.astral.sh/uv/guides/integration/pytorch/).
Linux x86_64/Python **3.14.7** is the verified reference platform.

A fresh `/tmp/datelier-checkpoint-clean` uv environment installs CPU PyTorch and
NumPy independently, then runs `scripts/checkpoint_feasibility.py`.
[Dependency report](evidence/phase11/checkpoint-dependency.json): nested
state-dict/primitive metadata, noncontiguous tensors and bfloat16 values pass;
physical fake-tensor storage is **meta** before value loading. Explicit modern
ZIP checkpoints use mapped CPU reads; legacy checkpoints also provide fake
metadata and explicit CPU values. Non-allowlisted objects fail restricted
loading. Every load supplies `weights_only=True` and `map_location="cpu"`;
no model is constructed and source bytes match. FakeTensorMode/mapped loading
follow [PyTorch's serialization documentation](https://docs.pytorch.org/docs/stable/notes/serialization.html).

Pyrefly **zero errors** (one existing suppression), focused array regressions
**13 passed**, Ruff lint/format (**346 files**) and diff whitespace pass.
The optional import boundary is confined to the feasibility script; ordinary
app import/startup does not import PyTorch. This verifies M11.4's dependency
entry gate. Checkpoint adapters, native tensor views, absent-extra diagnostics,
persistence/resource acceptance and M11.4 completion remain open.

The checkpoint adapter now opens `.pt`/`.pth`/`.ckpt` sources through a lazy typed
PyTorch boundary. FakeTensorMode retains primitive dict/list/tuple/byte metadata
and captures tensor paths, physical dtypes, shapes, layouts, strides, offsets and
logical byte sizes. Integer dictionary keys remain distinct from strings;
cyclic containers display reference locators. Configurable metadata node/depth
limits fail with local diagnostics. A Polars header table references tensors;
it does not hold tensor payloads. Unsupported/custom objects stay rejected by
restricted loading, with no unrestricted-loading or allowlist action offered.
The original hierarchy remains browsable, including scalar/empty checkpoints.

Typed options and integer node locators round-trip through the finite workspace
codec. Opening JSON/TOML record views retains its original scalar constraints;
checkpoint metadata lists do not expose an unrelated record-extraction control.
Tests explicitly forbid tensor-to-NumPy conversion while opening metadata,
verify physical fake storage, original bytes, cycles, malformed sources,
primitive metadata, limits, optional-extra diagnostics and lazy fresh-process app
imports. Focused checkpoint/object/array/session regressions **43 passed**;
Pyrefly **zero errors** (one existing suppression), Ruff lint/format (**353 files**)
and diff whitespace pass. Native nested-checkpoint metadata/tree smoke passes
**27 frames** with unchanged source bytes. Tensor value preparation, native
tensor controls and complete M11.4 acceptance remain open.

Explicit tensor preparation now leases restricted CPU checkpoint storage.
Modern files use read-only application access to mapped storage; legacy files
load CPU storage only when requested. Logical retention limits govern cached
checkpoint storage and discard oversized roots after a lease rather than remove
the ability to inspect them. Source stat checks surround loading/copying;
abandonment prevents obsolete preparation from publishing. No tensor is modified.

NumPy and tensor windows share pure axis/coordinate/budget planning and worker
display preparation. Exact copied windows preserve selected source coordinates,
noncontiguous axis order and ordinary dtypes. Bfloat16/float8 display values use
exact Float32 conversion of the bounded selection, with original UInt16/UInt8
storage bits kept beside them. Complex component plots, nonfinite gaps/spans,
scalar values and empty windows use the existing prepared renderer. A fixed
empty-axis NumPy scalar window now returns no values rather than an uninitialized
scalar. Both readers retain the 16,384-cell/8 MiB raw window budget.

Window/source/storage regressions **47 passed**: exact axes/strides/CPU mapping,
cache reuse, raw precision/bits, unsigned 64-bit values, complex/scalar/empty
windows, source changes, oversized legacy retention and abandonment. Sparse and
quantized metadata cannot be constructed by this verified FakeTensorMode path;
those files receive an unsupported object/layout diagnostic and remain
restricted, as do custom checkpoint objects. Dense state dictionaries and
primitive containers are the supported inspection path. Pyrefly **zero errors**
(one existing suppression), Ruff lint/format (**358 files**) and diff whitespace
pass. Native NumPy regression passes **78/35 frames** after shared window planning.
This is the tensor value foundation. Native controls, saved tensor windows,
resource/absent-extra acceptance and M11.4 completion remain open.

Native checkpoint Source browser now provides a virtual tensor-node selector,
shape/dtype/layout/stride/offset provenance, scalar/vector/matrix axes, fixed
coordinates, exact windows and complex components. **Prepare tensor values**
dispatches a file/revision-owned worker request; **Abandon tensor preparation**
discards its result without claiming executing storage reads have stopped.
The prepared renderer shows finite ranges, original coordinates, raw values and
numeric conversion diagnostics. Bfloat16/float8 storage bits are available in a
separate raw table. Primitive hierarchy browsing remains available beneath the
tensor view and directly for metadata-only containers.

Whole-session recipes save the tensor locator, axes/fixed positions/window,
complex component, node navigation and retention limit. Reopening restores
metadata/settings without reading tensor values or running ML. A restored view
immediately invalidates the former owner's jobs before rendering. Separate tabs
with equal tensor names own separate stores/revisions. Missing-source recovery
leaves other tabs usable and relinking remains metadata-only. Cached roots are
released on workers at closure or when retention requires eviction.

Focused checkpoint/session/window/array regressions **31 passed** (three upstream
sparse/quantized warning messages); Pyrefly **zero errors** (one existing
suppression), Ruff lint/format (**363 files**) and diff whitespace pass.
`checkpoint_views_smoke.py --output docs/evidence/phase11/checkpoint-views.json`
passes two fresh native processes: save **162 frames**, restore **105**. Real
mouse input chooses the nested cube tensor; keyboard input fixes axis **0** to
**1** and native preparation produces the expected **3×4** values. Additional
explicit bfloat16 preparation verifies display values and storage bits, then
returns to the cube using one cached CPU checkpoint load. Reopening proves no
value preparation before a native command. [Report](evidence/phase11/checkpoint-views.json)
and [reviewed screenshot](evidence/phase11/checkpoint-views.png) record readable
axis controls, tensor header table and spatial heatmap. Frame p95 is
**21.65/24.27 ms** under Linux Mesa; sources and temporary cleanup pass.
FileSession's **325 lines** were reviewed: source ownership/polling remain
cohesive while checkpoint reading, windows, jobs and rendering are separate.
Final resource, clean application/absent-extra and full-suite acceptance remain
open; M11.4 and Phase 11 are not yet marked complete.

The first full acceptance run found two regressions: an unused checkpoint scope
attempted cleanup submission after its external worker pool had already closed,
and the existing flat-table format fixture mistakenly treated the new checkpoint
metadata format as XML records. Checkpoint teardown now skips unused storage and
releases cached storage even when an external owner already joined its workers;
the flat-table fixture excludes non-tabular checkpoint metadata, which has its
own restoration fixtures. Worker loops also release completed task/cancellation
closures so source arguments, results and failed-task tracebacks cannot remain
pinned while idle. Abandoned fresh CPU loads clear storage from error tracebacks.
Behavioral weak-reference tests verify release of completed/failed source jobs.

Focused worker/file/workspace/checkpoint regressions **34 passed**, Pyrefly
**zero errors** (one existing suppression), Ruff lint/format (**364 files**) and
diff whitespace pass. Native checkpoint save/restore regression passes
**161/103 frames**. Final full-suite/resource/installed-application evidence is
still being collected before marking completion.
