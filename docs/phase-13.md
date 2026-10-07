# Phase 13 — Images, heatmaps, and detection annotations

Phase 13 is complete. Its scope is M13.1–M13.4 in [ROADMAP.md](../ROADMAP.md#phase-13--images-heatmaps-and-detection-annotations).
Phase 12 and the Inspect navigation follow-up are complete; the worktree was
clean at entry (`6cd56e2`). M13.1–M13.4 pass. Entries below retain the status at
each delivery slice; final acceptance records the complete milestone decision.

## Delivery steps

1. Establish original-resolution file and mapped-array image reads, orientation
   geometry, exact pixel windows, display-only channels and bounded worker
   publication. Verify this foundation before adding native Inspect controls,
   zoom/pan/pixel navigation and saved settings.
2. Prepare explicit exact or seeded sampled image collection profiles, with
   dimension/aspect and channel/color statistics, per-record diagnostics and
   stable file/view/source-row provenance. Render profiles without retaining
   every decoded image.
3. Extend the same navigation to numeric heatmaps with raw readouts, nonfinite
   markings, colormaps and independent display ranges/channels/slices.
4. Add source-preserving VOC, YOLO, COCO and Ultralytics adapters, explicit
   coordinate/class conventions and unambiguous image associations.
5. Render selectable overlays from multiple sources, annotation profiles and
   cross-file image comparisons. Verify saved recipes in a fresh process, full
   correctness, native geometry/selection and measured resource acceptance.

Each coherent code slice requires focused behavioral tests, Pyrefly, Ruff,
applicable native GUI verification, diff review and a commit before the next.
Milestone exit gates also require the full suite and their listed acceptance
cases. Existing Titanic usability gates retain their status.

## Acceptance budgets

Establish measurements against these fixture-specific targets before marking
resource gates passed. Use Linux/Python 3.14 and Mesa software OpenGL, as in the
existing evidence. GUI frame p95 remains **33 ms**. For a 2048×1536 RGB image,
metadata should prepare in **0.5 s**, the first visible original-pixel window in
**2 s**, and subsequent cached windows in **0.5 s**. The default window is at
most 1024×1024; CPU/GPU retention is configurable and byte bounded. Images
larger than retention remain accessible through windowing and leased temporary
storage. Source decoding can transiently exceed retained-cache budgets.

For a 100-image 256×256 mixed grayscale/RGB/RGBA collection, explicit exact
profiles should finish in **10 s** without retaining all decoded records.
The fresh-process peak RSS increase, including fixture preparation and profiles,
must remain under **96 MiB**. Decoded-file profiling should lease only one image
at a time and retain zero decoded bytes between records. A compressed image
array larger than its 1 MiB retention budget should extract its chosen member
once for the complete command and release it afterward.
Measure peak RSS, temporary disk use, cache retention and cleanup after close.
Use known-value array and equivalent cross-format annotation fixtures for
correctness; resource acceptance must not substitute for those checks.

Annotation acceptance uses 100 local image headers and 10,000 COCO boxes:
explicit parsing/association should finish in **5 s**, with fresh-process peak
RSS increase under **64 MiB** including fixture preparation. Preparation must
not decode image pixels or allocate temporary image/array caches. Sources remain
unchanged; overlays and profile rendering have separate M13.4 gates.

Final M13.4 resource fixtures use two independent 100×256² image collections:
exact or seeded-pixel common-bin comparison should finish in **20 s**, with
fresh-process peak RSS increase under **128 MiB**, including fixture creation.
Files retain only one decoded image at a time; two compressed members above
their 1 MiB budgets remain leased across both global passes, each extracted once
and released afterward. Peak temporary disk and source hashes are recorded.
Native overlay acceptance exercises **2,200 visible boxes**, the default **2,000**
display limit and an explicit increase to show all boxes; p95 remains **33 ms**.
These fixture budgets are established before running their measurements.

## Evidence

Planning (2026-10-07): inspected the current source, shared workers, references,
Inspect, mapped-array storage and persistence. Documentation links and diff
whitespace reviewed. Implementation and acceptance gates remain open.

### Original-pixel foundation (2026-10-07)

The image subsystem resolves file/view/source-row locators in workers and reads
metadata before pixels. PNG EXIF chunks are scanned without decoding IDAT;
Pillow's usual PNG `getexif()` fallback would otherwise decode the entire image.
TIFF's implicit load-time orientation is inverted in stored source pixels,
then all formats share the same explicit EXIF geometry. Display buffers are
separate from read-only original pixel windows. Palette images explicitly expand
to RGBA; grayscale, RGB/RGBA, bool, 16-bit and float values retain their decoded
values. Confirmed NHWC/NCHW mappings read only the chosen record/window while
preserving supporting-table identity after sort/filter.

Decoded files use leased temporary NPY storage; byte limits bound retained disk
data and CPU windows, including access to images larger than the budget.
Closure/replacement retire publication and release files after active leases.
Source decoding transiently uses Pillow memory; huge-image decompression-bomb
checks and unsupported modes produce diagnostics. PNG EXIF is limited to 1 MiB.
The file adapter displays the first frame, visibly recorded in metadata.

`uv run --offline --no-sync pytest tests/test_image_inspection.py
tests/test_array_mappings.py tests/test_array_storage.py tests/test_references.py`:
**56 passed**. Fixtures cover all eight PNG/TIFF orientations, header reads with
pixel loading forbidden (including EXIF after IDAT), exact grayscale/RGB/RGBA,
16-bit/float/bool/palette pixels, NHWC/NCHW sort alignment, missing/corrupt/changed
files, oversize retention/active-lease cleanup and obsolete file/view jobs.
Pyrefly: **zero errors**, one existing suppression. Ruff lint/format and diff
whitespace pass. Runs use `UV_CACHE_DIR=/tmp/datelier-uv-cache`, existing locked
dependencies and `POLARS_MAX_THREADS=8`.

Native prerequisite: `LIBGL_ALWAYS_SOFTWARE=1 POLARS_MAX_THREADS=8
OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 .venv/bin/python
scripts/image_texture_probe.py --output docs/evidence/phase13/image-texture.json`
passes on the desktop display with **Pillow 12.3.0**, Python **3.14.7**. A
2048×1536 RGB fixture opens metadata in **0.0007 s**, prepares a 1024×1024 original
window in **0.0599 s**, and a cached channel window in **0.0100 s**. It retains
**7,340,032 CPU bytes**, **4,194,304 GPU bytes**, and **9,437,312 temporary bytes**,
with one decode, six texture uploads over 30 frames and verified handle/file
cleanup. [Machine-readable report](evidence/phase13/image-texture.json) records
the probe. The sandbox cannot open `:0`; native verification uses desktop access.

This foundation does not yet add product controls. Native zoom/pan/readouts,
saved settings, collection statistics and all M13 exit gates remain open.

### Focused image Inspect and saved controls (2026-10-07)

Focused **Explore → Inspect** now routes Image fields and confirmed image-array
records to a worker-backed pixel canvas, beside aligned supporting fields.
Files/folders already use the same image-reference records. Native controls
include Fit, 1:1, pointer-centred wheel zoom, anchored drag-to-pan, composite or
individual channels, original-value hover readouts and configurable CPU/GPU/disk
retention. Oversized/zoomed-out views sample bounded overviews with explicit
stride labels; zooming exposes every original pixel, and readouts identify the
actual sampled coordinate. EXIF readouts also identify its original source
coordinate. Unsupported channels reset visibly to Composite on another record.

Image settings are optional typed workspace fields, with legacy defaults.
Headless opening/restoration starts no image decoding; focused visible records
prepare lazily. Settings and file/view/revision/reference changes retire pending
results. Cached source pixels remain separate from display buffers. Window
refreshes preserve an anchored drag, including movement outside the canvas.
GPU handles release before normal renderer shutdown and exception teardown.

Focused image/file/array/session/workspace/text-comparison checks: **72 passed**;
the additional image job/navigation/source/file subset: **42 passed**, including
executing-window retirement on revision changes and closure. The final full
suite: **778 passed in 20.78 s**, with three existing upstream checkpoint warnings.
Pyrefly: **zero errors**, one existing suppression. Ruff lint/format (**433 Python
files**) and diff whitespace pass. The full-suite run exposed a shutdown-order
failure when an empty image store queued unnecessary cleanup after the shared
pool had closed; cleanup now follows the existing array-store lifecycle and
the full suite passes.

`LIBGL_ALWAYS_SOFTWARE=1 POLARS_MAX_THREADS=8 OMP_NUM_THREADS=1
OPENBLAS_NUM_THREADS=1 .venv/bin/python scripts/image_inspect_smoke.py
--output docs/evidence/phase13` uses native mouse clicks for focused records,
Fit/1:1 and G-channel selection, native wheel zoom and drag-to-pan, and checks
known gradient pixel values. A fresh process restores its G channel and zoom/pan
recipe. It passes **212/80 frames**, with frame p95 **12.35/17.35 ms**, under 33 ms.
[Native report](evidence/phase13/image-native.json),
[focused image](evidence/phase13/image-inspect.png) and
[restored image](evidence/phase13/image-restored.png) record acceptance; both
screenshots were visually inspected.

`scripts/image_array_smoke.py --output docs/evidence/phase13` confirms an NHWC
mapping, sorts scalar labels, then uses native Next record input. Source rows
**1/2** retain known pixels **(20,5,9)/(30,5,9)** and labels **1/2**, independent
of display order and parent-file identity. Only labels and the chosen image
member are extracted; no image-file decoder is invoked. It passes **47 frames**,
frame p95 **11.59 ms**, with source preservation and GPU retention asserted.
[Array report](evidence/phase13/image-array-native.json) and the visually reviewed
[array Inspect](evidence/phase13/image-array.png) record results.

Original-resolution decoding/texture/navigation now satisfy the M13.1 entry
gate. Its collection summaries, exact color/channel statistics and measured
mixed-collection resources remain outstanding. M13.2–M13.4 remain open.

### Image collection profile foundation (2026-10-07)

Explicit worker commands now prepare scalar image profiles for all current
records, a row range, linked source-row selections or a seeded record sample.
Pixels are exact by default, with a separately configured deterministic pixel
sample. Sample seeds use original source-row identity, so sorting retains the
same chosen records and pixel samples. Results retain file/view/revision,
source references, mappings, scope/settings and per-asset identities.

The first pass prepares orientation-aware dimensions/aspect ratios and channel
moments; the second prepares shared channel bins from the same source identities.
Channels and physical modes/dtypes stay separate. Pixel-weighted means and
population deviations use extended-precision accumulation; original integer
extrema are retained, including UInt64 values that cannot be distinguished on a
double-precision plot axis. Those plots explicitly use scaled coordinates with
raw bounds. Null references, unresolved missing/ambiguous references and decode
failures remain separate per-record outcomes. A changed asset between passes
rejects the complete result rather than mixing moment and histogram snapshots.

Original grids are leased, with bounded spatial/sample batches and zero retained
decoded-file bytes for profiling. No source-sized presentation arrays or GPU
textures are created. Complete record/channel result tables remain available;
the renderer and resource acceptance are the next slice. Binding/restoring a
profile owner launches no work; only an explicit command dispatches it. Changes
to file/view/revision, settings, reference discovery or linked scope retire its
executing result, with safe abandonment and cleanup.

Image profile/source/job/reference tests: **53 passed in 0.50 s**. Fixtures cover
known grayscale/RGB/RGBA weighted counts, varied dimensions, oriented floats and
nonfinite values, UInt64 extrema/deviation/scaled bins, empty/null/ambiguous and
missing/corrupt collections, deterministic record/pixel samples after sorting,
NHWC/NCHW mappings with zero retention, changed snapshots and closure/scope
retirement. Pyrefly: **zero errors**, one existing suppression. Ruff lint/format
(**441 Python files**) and diff whitespace pass. This foundation adds no native
controls; M13.1 exit and resource gates remain open.

### Image collection profiles and M13.1 acceptance (2026-10-07)

Explore → Profiles now offers explicit image collection commands, exact/seeded
pixel scopes, complete virtual statistics/outcomes, dimension/aspect charts and
separate physical channel families with native legends. Outcomes select their
source row into Inspect. Mapped arrays expose payload profiling beside table
columns. Image-only folders use extension evidence to route to image tools;
mixed folders retain generic path interpretation. Display buffers and statistics
retain original values independently. Recipes preserve scopes, seeds, family and
tab; fresh-process restore starts no collection command or pixel decoding.

The compressed mapped member remains leased across both passes even when larger
than its retention budget, eliminating repeated per-record extraction. Worker
histograms include prepared plot buffers; rendering performs no pixel reads or
table-wide computation. Results preserve file/view/revision and source-row
identity, including equal row numbers in independent files.

Focused media/profile/persistence checks: **27 passed in 0.96 s**, in addition to
the **59** image/profile/navigation and **25** profile/workspace checks during
implementation. Final full suite: **796 passed in 22.64 s**, three existing
upstream checkpoint warnings. Pyrefly: **zero errors**, one existing suppression.
Ruff lint/format (**449 Python files**) and diff whitespace pass.
The existing `scripts/text_profile_navigation_smoke.py` regression passes
**536/59 frames**, including native text/numeric/category switches, explicit
corpus commands and independent-process idle restoration.

`scripts/image_profiles_smoke.py --output docs/evidence/phase13` uses native
selection, exact profile, Dimensions/Colors, RGB-family selection, outcome-to-
Inspect linking, sampled settings, explicit reprofile and expanded charts. The
known fixture has **24 exact pixels**, then **8/24 sampled pixels**, with
**4 ready / 1 null / 1 unresolved / 1 failed** records. Fresh-process restoration
preserves its recipe, remains idle, and passes the explicit rerun. Save/reopen
frame p95: **20.81/19.46 ms** over **440/80 frames**. Source hashes are preserved.
[Report](evidence/phase13/image-profiles-native.json),
[native profile](evidence/phase13/image-profile.png) and
[restored profile](evidence/phase13/image-profile-restored.png) record acceptance;
both screenshots were visually reviewed.

`scripts/image_array_smoke.py --output docs/evidence/phase13` extends the earlier
Inspect check with native mapped payload/profile commands. Sorted source rows
**1/2/0** retain labels and images; **12,288 pixels**, RGB red mean **20**, and only
two member extractions (labels/images) are verified. It passes **94 frames**, p95
**12.49 ms**. [Report](evidence/phase13/image-array-profile-native.json) and the
visually reviewed [array profile](evidence/phase13/image-array-profile.png) retain
the earlier Inspect evidence separately.

Fresh-process `scripts/benchmark_image_profiles.py --kind folder|array` exact and
`--sample` commands verify **100×256×256 images**, source hashes and temporary
cleanup. Exact folder/array times: **3.83/2.59 s**; sampled: **0.62/0.29 s**.
Folder peak RSS increases **18.64/20.27 MiB** (exact/sample), array
**35.35/35.20 MiB**, within 96 MiB. Folder profiling leases one decoded file,
peaks at **262,272 temporary bytes** and retains zero between records. The
**19,660,928-byte** compressed array member extracts once under **1 MiB** retention
and retains zero after completion. Exact **6,553,600** and sampled **102,400** pixel
counts are verified, including missing/corrupt folder diagnostics.
[Folder exact](evidence/phase13/image-folder-resources.json),
[array exact](evidence/phase13/image-array-resources.json),
[folder sampled](evidence/phase13/image-folder-sample-resources.json) and
[array sampled](evidence/phase13/image-array-sample-resources.json) record results.

`scripts/image_profile_live_benchmark.py` uses a native explicit folder command:
**3.84 s**, **350 running frames**, p95 **11.70 ms**, peak RSS increase
**15.56 MiB**, bounded preview CPU/GPU **131,072 bytes** each. The initial check
exposed image-only folder routing to generic text tools; the role correction and
rerun pass. [Live report](evidence/phase13/image-profile-live.json) records this
responsive run. All native commands use the established Mesa/software OpenGL
environment; accelerated rendering remains unverified.

M13.1 deliverables, correctness, native restoration and resource exits pass.
Numeric heatmaps, annotation adapters/overlays and cross-file image comparisons
remain outstanding in M13.2–M13.4.

### Numeric heatmap foundation (2026-10-07)

Confirmed Numeric heatmap mappings now prepare one chosen scalar plane with
optional fixed-axis coordinates, bounded original-pixel windows and the same
source-row identities as image Inspect. Metadata represents channel counts
without generating a name for every channel. A two-million-channel fixture
opens metadata without reading payloads and retains only **12 bytes** for its
chosen one-pixel raw/RGBA buffers. Numeric mappings never become encoded RGB.

Shared display normalization retains raw integer extrema, including nearby
UInt64 values, and uses extended precision for negative/extreme float ranges.
Automatic bounds describe the prepared window; explicit finite bounds clip only
colors. Constants use the midpoint; NaN/±Inf use magenta. Linear grayscale,
blue/white/red, blue/green/yellow and purple/gold ramps are independent of raw
values, slices and statistics. Phase 11 slice preparation shares this helper,
while vector/complex/raw presentations remain available. Encoded image channel
views now mark nonfinite values only in the chosen channel.

Focused heatmap/array/image/profile/persistence checks: **77 passed**. They cover
signed/constant/extreme/nonfinite values, precise UInt64 colors, N-depth-C-W-H
slice transpose, sorted record identity, independent fixed coordinates, invalid
channels/slices/ranges, source hashes, read-only buffers and legacy recipes.
Pyrefly: **zero errors**, one existing suppression; Ruff lint/format (**451 Python
files**) and diff whitespace pass.

The existing native `scripts/array_views_smoke.py` regression passes **78/35
frames**, p95 **12.84/12.32 ms**, with native fixed-index/slice input, explicit
preparation, fresh-process idle metadata restore, source preservation and cleanup.
[Report](evidence/phase13/heatmap-foundation-native.json) records the run.
M13.2 entry passes. New native heatmap channel/slice/colormap/range controls and
its exit/restoration gates remain open.

### Numeric heatmap controls and M13.2 acceptance (2026-10-07)

Explore → Inspect routes confirmed Numeric heatmap records to the original-pixel
canvas, with channel indices, fixed-axis slice positions, four linear colormaps,
automatic prepared-window bounds or explicitly applied limits, Fit/1:1,
pointer-centred zoom and exact raw hover values/full source coordinates.
Nonfinite scalars are opaque magenta. Display choices retire obsolete worker
windows, preserve original dtype/data and leave statistical bounds unchanged.
Source array slices expose the same colors/range controls; explicit Prepare
slice applies them. Native array rendering uses the same linear ramp stops as
worker-prepared RGBA pixels. Vector/raw views remain available.

Source-coordinate, window, raw/range and legacy workspace checks pass. A
2048×3072 float64 NPY fixture under 1 MiB CPU retention produces a labeled
stride-4 1024×1024 overview with **786,432 retained bytes**, then retrieves the
previously unsampled exact pixel as a one-pixel window. The source memmap opens
without member extraction or image-file decoding. Focused heatmap/image/array/
checkpoint/workspace subset: **46 passed in 3.92 s**. Full suite: **806 passed in 20.93 s**
(three existing checkpoint warnings). Pyrefly: **zero errors**, one existing
suppression; Ruff lint/format (**455 Python files**) and diff whitespace pass.

`scripts/heatmap_smoke.py --output docs/evidence/phase13` uses a saved docked
full-panel layout as its fixture. Native inputs choose channel **1**, depth
**1**, blue/white/red colors and display **−25…25** independently of raw finite
bounds **−47…90**; Fit, hover (**−10** at **(10,10)**) and wheel zoom pass. Three
NaN/±Inf values are marked. Sorted source row **1** keeps supporting label **1**.
Native save/reopen passes **432/80 frames**, p95 **11.10/11.41 ms**, with
**18,432 CPU / 6,144 GPU bytes** retained. Fresh-process reopening reads metadata
only, then native **Table preview → Prepare saved array records** restores the
scalar table/history and saved display recipe. Pixel preparation follows
focused visibility; no collection profile runs. Source hashes remain unchanged.
[Report](evidence/phase13/heatmap-native.json),
[native heatmap](evidence/phase13/heatmap-inspect.png) and
[restored heatmap](evidence/phase13/heatmap-restored.png) record acceptance; both
screenshots were visually reviewed.

`scripts/array_views_smoke.py` still passes native fixed-index/explicit slice and
fresh-process metadata restoration (**78/35 frames**, p95 **14.19/13.46 ms**).
[Array regression report](evidence/phase13/heatmap-array-native.json) records
source preservation and cleanup. README now documents image collection profiles
and numeric display controls. The existing native encoded-image Inspect regression
also passes **212/80 frames**, p95 **12.82/17.93 ms**, with Fit/zoom/pan, channel
selection, raw readouts, saved settings and source hashes verified.
M13.2 deliverable, correctness and native
restoration exits pass; M13.3–M13.4 remain open.

### Annotation conventions and VOC/YOLO foundation (2026-10-07)

Inspected primary format references before implementing adapters:
[VOC development kit](https://www.robots.ox.ac.uk/~vgg/projects/pascal/VOC/voc2008/htmldoc/index.html)
specifies top-left pixel (1,1) and named xyxy boxes;
[COCO format](https://github.com/cocodataset/cocodataset.github.io/blob/master/dataset/format-data.htm)
specifies 0-indexed top-left xywh and separate image/category IDs;
[Ultralytics detection format](https://docs.ultralytics.com/datasets/detect)
specifies normalized centre xywh, zero-based classes and YAML split paths;
[its label path helper](https://docs.ultralytics.com/reference/data/utils/#ultralytics.data.utils.img2label_paths)
replaces the last images directory with labels and the suffix with .txt.
Manifest root resolution will be explicit: Datelier defaults relative roots to
the manifest directory and permits an override, rather than depending on an
Ultralytics installation's global dataset directory. Image-list `./` paths use
the list file's directory. Local parsing does not import Ultralytics or execute
manifest download fields. PyYAML 6.0.3 is already locked through the base
Hugging Face Hub dependency; a direct dependency with SafeLoader will be established and
tested in the manifest slice. [PyYAML documentation](https://pyyaml.org/wiki/PyYAMLDocumentation)
defines its standard-data-only loader.

The first annotation slice adds immutable original box/class/source/issue
records, guarded read-only file snapshots, VOC XML and YOLO detection text.
VOC exposes one-based inclusive xyxy (default) and explicitly selected zero-based
pixel-edge xyxy for exporters using that convention. Inclusive minima subtract
one; maxima remain image edges. One-pixel and fractional boxes are tested.
YOLO retains normalized values until original image dimensions are supplied.
Trailing confidence is an explicit extension; invalid syntax retains original
text/XML and line/object locations. Unknown supplied class mappings are diagnostic.
Nonpositive/nonfinite geometry is rejected on conversion; out-of-bounds geometry
is retained with warnings, never clipped. Source/class/index/score provenance
stays distinct from display orientation.

`pytest tests/test_annotation_readers.py tests/test_import_xml.py
tests/test_image_inspection.py`: **79 passed in 0.53 s**, including equivalent
VOC/YOLO boxes, all eight EXIF edge transforms, optional scores/flags, explicit
index choices, empty labels, invalid classes/rows/geometry, duplicate XML fields,
DTD/entity rejection and changed snapshots. Pyrefly: **zero errors**, one existing
suppression; Ruff lint/format and diff whitespace pass. This slice introduces no
GUI controls. COCO/manifests, association and M13.3 exit gates remain open.

### COCO and local Ultralytics manifest foundation (2026-10-07)

COCO dataset JSON retains original xywh, sparse image/category IDs, scores,
crowd flags and source-array locations. Identity joins are exact; duplicate image
or category headers fail as ambiguous, while orphan/duplicate/invalid annotation
records retain diagnostics and original representations. Unknown category IDs
remain visible. Strict shared JSON decoding rejects duplicate fields/nonstandard
constants before interpretation.

Ultralytics YAML now uses a direct **PyYAML ≥6.0.3,<7** base requirement; `uv add`
regenerated the lock, keeping the existing **6.0.3** and all package versions.
`uv lock --check --offline` passes. The isolated SafeLoader rejects duplicate
keys (including merges) and arbitrary object tags, while standard aliases work.
Local splits support directories, individual images, lists of split paths and
UTF-8 image-list files, with explicit dataset-root override. Image headers share
the original image metadata reader, including original dimensions before EXIF,
and never decode pixels. Download fields remain source data and get a diagnostic.

Empty, missing and unreadable labels stay distinct; a missing file does not imply
a negative image. Shared label stems across image extensions require explicit
association, with both raw records and ambiguity retained. Repeated image entries
across splits share boxes and remain diagnostic. `nc` without names stores a
declared count and only encountered names, avoiding a two-million-name metadata
allocation. Guarded file snapshots and final source-identity checks reject
changes between image/label records, without publishing mixed data.

Focused annotation/JSON/object/image/dependency/profile checks: **135 passed in
17.22 s**; the final expanded dataset-reader subset: **16 passed**. These include
equivalent COCO boxes, noncontiguous IDs, unknown/orphan/duplicate annotations,
header-only oriented image metadata, list/alias/root path handling, empty/missing
labels, shared-stem ambiguity, malformed/unsafe YAML, unchanged file sets/hashes
and mid-command external edits. Pyrefly: **zero errors**, one existing suppression;
Ruff lint/format (**469 Python files**) and diff whitespace pass. No GUI behavior
changes in this foundation slice. M13.3 entry passes; explicit image association,
native source controls and its exit gate remain open. M13.4 remains open.

### Explicit image association foundation (2026-10-07)

Typed source recipes now prepare annotations against current image references
or confirmed array records. Match choices are resolved physical paths, unique
filenames/stems or an explicit key column; duplicate candidates remain ambiguous.
Explicit source-image-key → source-row mappings capture the current logical key
and image reference. Sorting preserves them; excluded rows and changed references
(including the same basename in another directory) require confirmation instead
of reassigning boxes. Logical references within the source root keep relinks
independent of absolute root spelling.

Prepared boxes carry file, record-view, revision, source-row, field, source recipe,
annotation path/ordinal and annotation-image key identity. Original geometry and
EXIF-oriented continuous edge geometry stay separate. Declared dimension
mismatches are diagnostic; conversion uses original target dimensions without
clipping source boxes. Mapped array association reads headers and scalar keys,
without member extraction. Missing/corrupt targets, invalid boxes and absent
manual keys retain outcomes. Unreadable annotation sources preserve other usable
sources. Final snapshots retire a source edited after its association, including
failed files in directory scopes; commands never publish mixed source geometry.

VOC/YOLO folders retain relative label keys and per-file provenance. Parsing,
target-key indexing, headers and box preparation occur outside rendering;
bounded index batches yield and check abandonment. Module responsibilities were
reviewed at the 300-line trigger: matching, per-source association and combined
commands now have separate typed boundaries.

Focused association/adapter/image/array checks: **84 passed in 0.57 s**. Fixtures
cover duplicate filenames, explicit/sorted/excluded/changed row mappings,
namespace collisions between equal rows in separate files, all original/oriented
geometry, key/path and hierarchical folder matches, dimension mismatch,
missing/corrupt targets, one failed source beside usable sources, array IDs with
payload extraction forbidden, abandonment and external edits after association.
Pyrefly: **zero errors**, one existing suppression; Ruff lint/format (**476 Python
files**) and diff whitespace pass. No GUI changes in this foundation. Explicit
native loading/mapping controls, saved recipes and M13.3 exit remain open;
overlays, profiles and image comparisons remain open in M13.4.

### Annotation worker and saved-recipe foundation (2026-10-07)

Annotation commands now use the editor's shared bounded executor, with explicit
dispatch, progress, abandonment and file/view/revision/settings ownership.
Binding, opening and restoring a session do not parse labels. Changed references,
recipes or closed tabs retire executing results. Confirmed manual row pins become
the saved recipe without invalidating the result that established them. Legacy
image settings retain empty annotation defaults. Relative image roots use the
annotation file/folder, and dataset-root overrides use the manifest directory.

Focused worker, association, image/profile, shared-job and session-recovery checks:
**69 passed in 1.44 s**. They cover late completion after six context changes,
explicit dispatch, recipe confirmation and fresh-session restoration with label
reading and image pixel decoding forbidden. Pyrefly: **zero errors**, one existing
suppression; Ruff lint/format (**479 Python files**) and diff whitespace pass.
The native mapped-image/profile regression passes **94 frames**, p95 **13.22 ms**,
including sorted row alignment, native Next/profile commands and source hashes.
The broader encoded-image and heatmap input scripts failed during automated
zoom/channel/slice input in this run; their earlier milestone evidence remains,
and these attempts do not establish new interaction evidence. New annotation
controls, native mapping/restoration and M13.3 exit remain open.

### Native annotation association and M13.3 acceptance (2026-10-07)

Explore → Inspect now has explicit local source/path/format controls, VOC index
choices, optional YOLO scores/classes, manifest roots, path/filename/stem/key-field
matching and source-image-key → stable source-row mappings. Reconfirming a mapping
retires only its old reference pin. Loading stays explicit, with progress and safe
abandonment. Virtualized association/box/issue tables retain original values,
classes, scores, locations, missing-label status and diagnostics. Clicking a
matched key links its source row and focuses the image. Scroll-bounded results
leave the image canvas accessible. Parsing, indexing and headers stay in workers.
Rendering consumes prepared geometry. Source settings are saved; restore is idle.

The native fixture establishes a local discovery root and waits for its index;
issuing a command before discovery finished correctly retired the earlier result
in the initial attempt. `scripts/annotation_smoke.py` verifies native Add/path,
manual key/row confirmation, explicit commands and linked selection on sorted rows.
VOC/YOLO/COCO/manifest all produce original **(20,10,60,30)** and EXIF-6 oriented
**(10,20,30,60)** boxes for source row **1**, retaining an invalid VOC box issue and
a distinct missing manifest label. Save/reopen passes **420/142 frames**, p95
**13.72/13.28 ms**. Fresh-process recipes reopen without annotation work before
the native command. Source hashes pass; both screenshots were visually reviewed.
[Native report](evidence/phase13/annotations-native.json),
[Inspect](evidence/phase13/annotations.png),
[reopened Inspect](evidence/phase13/annotations-restored.png).

`scripts/benchmark_annotations.py` prepares **100 image headers / 10,000 boxes**
in **0.158 s**, fresh-process peak RSS increase **27.26 MiB**, with pixel loading
forbidden, no temporary caches and unchanged file sets/hashes.
[Resource report](evidence/phase13/annotations-resource.json).

Focused controls/association/job/workspace/record checks: **32 passed in 0.96 s**.
M13.3 full suite: **867 passed in 24.61 s**, with three existing PyTorch warnings.
Pyrefly: **zero errors**, one existing suppression; Ruff lint/format (**487 Python
files**) and diff whitespace pass. Responsibilities were reviewed near the
300-line trigger: source edits, recipe validation and prepared tables have separate
modules; the native harness retains one coherent multi-process scenario.
M13.3 deliverable and exits pass; M13.4 entry passes. Overlays, annotation profiles
and cross-file image comparisons remain open, so Phase 13 remains incomplete.

### Prepared box profile and overlay foundation (2026-10-07)

Association commands now index boxes by complete file/view/revision/source-row/
field origin, so rendering can retrieve one image's boxes without scanning a
collection. Pure overlay choices distinguish source and physical class IDs,
optional score thresholds and unscored boxes. Screen-edge transforms, viewport
visibility and point picking consume the prepared oriented geometry.

Explicit shared-worker profiles summarize the associated snapshot: class counts,
original width/height/area/aspect statistics and exact histograms, complete linked
box rows and separate image/label/association/error/warning counts. Missing labels
remain distinct from present labels without boxes. Failed sources retain quality
outcomes. Changing prepared sources or bins retires profiles; binding never starts
computation. Profile preparation reads no annotation/image files.

Focused profile/geometry/association/reader/image checks: **59 passed in 0.42 s**;
the final association subset also passes after adding the prepared-index invariant.
Fixtures cover known class/size/quality statistics, empty failures, all eight EXIF
orientations under zoom/pan/picking, class/source/score identity and late worker
completion after retirement. Pyrefly: **zero errors**, one existing suppression;
Ruff lint/format (**492 Python files**) and diff whitespace pass. No new GUI behavior
in this foundation. Native overlays/profiles, saved display controls and cross-file
image comparisons remain open in M13.4.

Verification repair: the final type-check output was read after the foundation
commit and reported two string revision IDs in its new tests. The fixtures now
use UUIDs; Pyrefly and focused checks were rerun before starting native UI work.

### Native overlays and annotation profiles (2026-10-07)

Focused image canvases now render source-colored class/score overlays from the
prepared origin index, with view-only source and physical class filters, optional
score thresholds, explicit inclusion of unscored boxes and adjustable visible-box
limits. Truncation is labeled. Picking links the image's stable source row;
Ctrl-click cycles overlapping sources. Dragging pans without selecting a box.
Selections retire with obsolete preparation or a different focused image.
Unknown observed class IDs are included in the worker-prepared filter metadata,
alongside declared classes and their diagnostics. No annotation reads occur in
rendering. Overlay display changes preserve association results.

Detection annotations → Profiles explicitly prepares exact classes, original
size/aspect histograms, quality counts and linked box records. Worker-prepared
class row IDs allow class-count selection without table-wide frame computation.
Sources, profiles and overlay display settings have independent saved recipes;
restoration starts neither annotation loading nor profiles. Cache/provenance
controls were separated from the image view at its 300-line responsibility review.

`scripts/annotation_smoke.py --overlays --output docs/evidence/phase13` passes
**1305/291 frames**, p95 **13.35/13.97 ms**. It verifies equivalent EXIF-6 boxes
from four formats, native source toggles leaving three visible sources, picking
and overlap cycling, screen-edge alignment under native zoom/pan, size charts,
known class/size statistics and linked selection. Fresh-process reopen restores
source toggles, profile tabs and viewport while leaving work idle until explicit
commands. The input harness now sends both key and modifier events, separates
modifier release from text entry and focuses the dock before each click; initial
attempts exposed those harness input/focus failures. Source hashes pass, and both
screenshots were visually reviewed.
[Native report](evidence/phase13/box-overlay-native.json),
[overlay Inspect](evidence/phase13/box-overlay.png),
[reopened overlays](evidence/phase13/box-overlay-restored.png).

The extended header-only resource fixture prepares **10,000 boxes** in **0.243 s**
and exact profiles in **0.090 s**, peak RSS increase **39.46 MiB** including
fixture/association/profile buffers. Class counts are **3400/3300/3300** with
100 linked image IDs each; means are width **20**, height **40**, area **800**,
aspect **0.5**. Pixel loading is forbidden and no temporary caches are allocated.
[Profile resource report](evidence/phase13/box-profiles-resource.json).

Focused display/job/workspace checks: **50 passed**; final association/profile/
workspace/image/control/job checks: **43 passed in 1.34 s**, including unknown
class filter metadata and persisted view choices without reassociation. Pyrefly:
**zero errors**, one existing suppression; Ruff lint/format (**497 Python files**)
and diff whitespace pass. This native overlay/profile slice passes. Cross-file
image comparisons, larger native overlay resources and final M13.4/full-phase
acceptance remain open.

### Shared physical image-bin foundation (2026-10-07)

Image collection preparation now separates the source-aligned first-pass scan
from histogram completion. Typed scans retain metadata, row/channel outcomes and
moments, without decoded grids. Completion accepts read-only physical bounds for
dimensions and each mode/channel/dtype family; source summaries keep their own
original extrema and moments. The normal profile command keeps its existing
two-pass behavior and compressed-member lease. Scan, histogram and command
responsibilities now have separate modules below the 300-line review trigger.
This is the foundation for comparisons using common bins rather than combining
incompatible independently binned pixel counts.

Focused image/profile/job/workspace/window checks: **55 passed in 1.80 s**,
including known shared edges/counts with unchanged source statistics and identity,
seeded scope alignment, exact integer/nonfinite values, edited sources between
passes and compressed-member leases. Pyrefly: **zero errors**, one existing
suppression; Ruff lint/format (**499 Python files**) and diff whitespace pass.
The first extraction of the scan missed a bounds-variable replacement and a
test's patched lookup moved modules; both were fixed within this step and checks
rerun. No source/display behavior is changed by the scan refactor.

Resource regressions on 100×256² images pass: folder **2.76 s**, RSS increase
**18.31 MiB**, one decoded file at a time and zero retained bytes; compressed array
**2.92 s**, **35.20 MiB**, one **19,660,928-byte** extraction above its 1 MiB cache,
zero retained bytes afterward. Hashes and cleanup pass. The native mapped-image/
profile regression passes **94 frames**, p95 **13.65 ms**, with original pixels,
sorted **[1,2,0]** profile identity, **12,288** pixels and red mean **20**.
Its GPU assertion now bounds the visible window rather than requiring the whole
64×64 record in a shorter dock. One frame-budget attempt overlapped background
verification and failed; the final isolated run passes the 33 ms target. Cross-file
commands, saved comparison mappings and final M13.4 acceptance remain open.

### Scoped cross-file image comparison foundation (2026-10-07)

Explicit comparison commands now scan mapped image fields/views with independent
record/pixel scopes, then complete every source's dimension and physical
mode/channel/dtype histograms against common bounds. Weighted original channel
statistics remain per source. Prepared count/proportion curves distinguish absent
families from zero values. Metadata, null/unresolved/decode outcomes, sampling
provenance and complete file/view/revision/row identities remain available.
Compressed members stay leased across both global passes, including members above
their cache budgets. Final snapshots recheck earlier contributors after later ones
finish; source edits reject mixed results. No data files are changed.

Shared-worker binding starts no work. Changed or closed contributors retire
results and pending selections without rerunning. Exact dimension-bin selection
uses prepared records and current revisions, preserving sorted table positions;
publication follows the existing 10,000-row limit while reporting all matches.

Focused comparison/image/profile/job/column/text checks: **38 passed in 1.71 s**.
Fixtures cover known shared edges, weighted color means and proportions, absent
RGBA families, null/missing/corrupt records, seeded/linked scopes under sorting,
equal row numbers in independent files, one compressed extraction with zero
retention, late external edits, abandonment, parser completion after source closure,
closed-source selections and bounded publication. Pyrefly: **zero errors**, one
existing suppression; Ruff lint/format (**506 Python files**) and diff whitespace
pass. Production responsibilities are split by recipe, inputs/results, preparation,
selection and job lifecycle; the larger behavioral test fixture remains cohesive.
This foundation changes no GUI behavior. Editor/session integration, native
comparison controls/restoration and final M13.4 acceptance remain open.

### Editor/session image comparison integration (2026-10-07)

The editor now owns image comparison recipes, an active recipe/view and shared
jobs. Inputs include independent file/view revisions, reference settings, selected
rows and borrowed array stores/catalogs/mappings. Numbered source labels remain
distinct when filenames match. Results bind and retire during editor polling
without implicit preparation. Dimension selections activate the correct parent
tab/record view and table position. Closing a source prunes its mappings immediately
for safe same-frame saving; polling also handles closed record views.

Version-two sessions persist comparison mappings, scope/pixel options and view
choices, with empty legacy defaults. Derived curves/pixel caches remain excluded.
Reopening stays idle; missing-source recovery preserves other usable tabs and
recipes, and relinking does not profile implicitly. Input construction/binding has
a separate image-session helper, keeping lifecycle ownership in the editor.

Focused editor/session/image/column/text comparison checks: **25 passed**.
Tests cover legacy decoding, explicit dispatch, correct file/table linking, saved
view settings, reopen with comparison preparation forbidden, partial recovery,
relink and immediate closed-source recipe pruning. Pyrefly: **zero errors**, one
existing suppression; Ruff lint/format (**508 Python files**) and diff whitespace
pass. This step adds no visible GUI controls. Native comparison views, restoration
and final M13.4 acceptance remain open.

### Native image comparisons and restoration (2026-10-07)

Compare files now includes Images with explicit file/field or confirmed array
view mappings, independent collection/pixel scopes and common physical bins.
Dimensions and mode/dtype color families have native source legends and count or
proportion curves. Source statistics retain original weighted values; absent
families and sampling/outcomes remain visible. Scaled numeric axes explain their
original bounds. Dimension-bin commands link sorted rows in the correct source;
record outcomes activate its tab/view and open the selected image in Inspect.
Unavailable saved fields require an explicit choice rather than silently choosing
another mapped member. Main comparison navigation also persists with legacy
Columns defaults. Restoration starts no collection profiling.

`scripts/image_comparison_smoke.py` verifies native mapping checkboxes, two common
bins, explicit preparation, weighted red means **23.333333/55**, shared width
edges **32/64/96**, count controls, Statistics, sorted-source bin selection and
Records-to-Inspect pixels **(70,20,30)**. Save: **657 frames**, p95 **13.10 ms**;
fresh-process reopen: **106 frames**, p95 **12.84 ms**. The reopened Images/Colors
view is idle until its native Prepare command. Source hashes remain unchanged.
The smoke harness uses captured native popup item rectangles for source/bin
choices after keyboard navigation proved unreliable. Both final screenshots were
visually reviewed; legends, axis labels and scope captions are visible.

Focused editor/comparison/image/profile/workspace checks: **47 passed**. Tests
also cover correct record owner/focus, stale record rejection, saved main tab
defaults and unavailable mapped-member rejection without another extraction.
Pyrefly: **zero errors**, one existing suppression; Ruff lint/format (**512 Python
files**) and diff whitespace pass. Production controls, chart rendering and view
ownership are separated; the native scenario remains one cohesive script.
Evidence is in [image-comparison-native.json](evidence/phase13/image-comparison-native.json)
and its save/reopen screenshots. Larger native overlay resources, comparison
resource measurements and final M13.4/full-phase acceptance remain open.

### Bounded annotation class links (2026-10-07)

Class links now follow the existing 10,000-row publication limit, retaining the
complete class count and explaining the first-N image selection. Previously a
larger class could raise the selection limit exception from a frame callback.
Focused annotation profile/workspace checks: **16 passed**, including 10,003
matching rows, bounded publication and stale-file rejection. Pyrefly: **zero
errors**, one existing suppression; Ruff lint/format (**512 files**) and diff
whitespace pass. Native cross-format class/profile/overlay regression and idle
fresh-process restore pass **1,305/291 frames**, p95 **12.50/12.42 ms**; source
hashes remain unchanged. See [regression evidence](evidence/phase13/box-overlay-link-regression.json).
Final comparison and larger-overlay resource budgets above were established
before their measurements; those gates remain open.

### Dense overlays and comparison resources (2026-10-07)

The initial 2,200-box native fixture exceeded the 33 ms frame budget: drawing every
class/score label reached **59.96 ms** and concealed the image. Overlap avoidance
alone reached **37.27 ms**. Screen label occupancy now retains non-overlapping
labels with selected-label priority, a shown/available count and an explicit
persisted Show overlapping box labels control. All boxes and original class/score
records remain available. Cached viewport scenes avoid rebuilding geometry and
label placement every frame; source/revision/record, viewport/bounds, filters,
selection, font identity/metrics and alpha changes invalidate them. Closing clears
the scene. GUI rendering and scene layout have separate, bounded responsibilities.
Forcing every overlapping label remains available and can be slower in dense views.

`scripts/box_overlay_resources.py` now passes **650 native frames**, including
120 steady frames at the default 2,000-box limit and 120 with all **2,200 boxes**
after a native limit increase. Class and score labels stay enabled; automatic
overlap avoidance yields **30.71 ms p95**, within the established 33 ms target.
Native overlapping-label on/off choices, count notices, retained texture bound
of **1 MiB** and unchanged source hashes pass. The final screenshot was visually
reviewed. Native zoom/pan/source-toggle/pick/profile and fresh-process restore
regressions pass **1,305/291 frames**, p95 **12.75/12.68 ms**, with geometry and
original source-row identity intact. Evidence: [large overlay](evidence/phase13/box-overlay-large-native.json)
and [cache regression](evidence/phase13/box-overlay-cache-regression.json).

`scripts/benchmark_image_comparisons.py` runs each case in a fresh process. All
cases compare two independent **100×256² RGB collections**, include fixture
creation in peak RSS, preserve weighted red means **49.5/99.5** and use common
**0–149** color bounds with normalized proportions:

| Sources / pixels | Time | RSS increase | Peak temporary storage |
| --- | ---: | ---: | ---: |
| Files / exact | 5.65 s | 19.05 MiB | 196,736 bytes, one image |
| Files / sampled | 0.82 s | 21.11 MiB | 196,736 bytes, one image |
| Compressed arrays / exact | 5.34 s | 48.84 MiB | 39,321,856 bytes |
| Compressed arrays / sampled | 0.60 s | 51.35 MiB | 39,321,856 bytes |

Exact commands profile **6,553,600 pixels per source**, sampled commands
**102,400 per source**, with explicit seeded provenance. File cases preserve
separate corrupt/missing outcomes and retain zero decoded bytes between records.
Each compressed member extracts once across both global passes despite its 1 MiB
cache budget; both release to zero retained bytes. All temporary paths disappear
after close and source hashes remain unchanged. The 20 s/128 MiB comparison
budgets pass. Four `image-comparison-*-resources.json` reports retain raw measures.

Focused layout/annotation/profile/workspace/comparison checks: **28 passed**,
including crossing/touching screen cells, failed reservation isolation and new/
legacy overlap-control persistence. Pyrefly: **zero errors**, one existing
suppression; Ruff lint/format (**517 Python files**) and diff whitespace pass.
This hardening/resource step passes; final M13.4/full-phase suite acceptance
remains open until its final verification.

### Final M13.4 and Phase 13 acceptance (2026-10-07)

After the verified resource-hardening commit `6ec1c80`, the full suite passes
**896 tests in 22.85 s**, with three existing restricted-checkpoint Torch warnings.
`uv run pyrefly check` reports **zero errors**, one existing suppression;
`uv run ruff check .` and `uv run ruff format --check .` pass (**517 Python files**).
`uv lock --check --offline` passes with **46 packages**. The worktree was clean
before this documentation-only acceptance update. Markdown links, milestone
consistency and diff whitespace are reviewed before its commit.

M13.1–M13.3 retain their recorded original-pixel, heatmap, format-association,
native restoration and measured resource gates. M13.4 now passes selectable
multiple-source class/score overlays, preserved EXIF/zoom/pan geometry, exact
annotation profiles, bounded linked rows and common-bin image dimension/color
comparisons with independent scope/provenance. Saved mappings and view choices
restore idle in fresh processes; explicit commands rebuild results. Known-value
fixtures, source hashes, stale/closed-result rejection, cache cleanup, original
record alignment and measured comparison/overlay budgets all pass as recorded
above. No image or annotation source is modified by inspection or restoration.

All Phase 13 deliverables and exit/verification gates pass. These are Linux,
Python 3.14 and Mesa software OpenGL fixture measurements, not a general capacity
guarantee. Showing all overlapping labels can still be slower; the default avoids
overlap with a visible count and an explicit override. Accelerated rendering and
other platforms retain their existing unverified status. Existing Titanic
usability gates remain unchanged. Phase 14 audio inspection and integrated
acceptance remains open as the next authorized sequence.
