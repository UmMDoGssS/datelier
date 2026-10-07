# Phase 13 — Images, heatmaps, and detection annotations

Phase 13 is in progress. Its scope is M13.1–M13.4 in [ROADMAP.md](../ROADMAP.md#phase-13--images-heatmaps-and-detection-annotations).
Phase 12 and the Inspect navigation follow-up are complete; the worktree was
clean at entry (`6cd56e2`). M13.1 passes; M13.2–M13.4 remain open.

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
