# Phase 13 — Images, heatmaps, and detection annotations

Phase 13 is in progress. Its scope is M13.1–M13.4 in [ROADMAP.md](../ROADMAP.md#phase-13--images-heatmaps-and-detection-annotations).
Phase 12 and the Inspect navigation follow-up are complete; the worktree was
clean at entry (`6cd56e2`). No Phase 13 exit gate has passed yet.

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
