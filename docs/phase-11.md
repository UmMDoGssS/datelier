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
