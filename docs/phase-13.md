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
