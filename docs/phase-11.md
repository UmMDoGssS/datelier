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
