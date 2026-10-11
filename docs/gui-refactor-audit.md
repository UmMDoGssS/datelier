# Fresh GUI refactor audit

This audit concerns the replacement GUI and its application coordination layer.
The acceptance contract and detailed measurements are in
[gui-overhaul.md](gui-overhaul.md). Historical phase evidence does not substitute
for replacement-GUI verification.

## Architecture and responsibility

The GUI contains 139 Python modules, 14,727 lines and 280 classes; application
coordination contains 57 modules, 6,377 lines and 74 classes at the audit snapshot.
These counts describe responsibility separation, not an acceptance metric.

- `Component.render(FrameContext)` is the rendering contract. Page, Panel, Tab,
  container, field, viewport, record and profile families specialize it. Containers
  render direct children; explicit assembly supplies the hierarchy and lifetime.
- Whole editor/file controllers enter rendering only at bootstrap and the three
  shell composition modules. Leaves receive tool controllers, typed prepared
  objects, read/write bindings and commands. Architecture tests enforce both this
  boundary and the absence of GUI/native imports in application/domain packages.
- Route maps, profile/record families, source adapters and injected factories
  replace cross-feature dispatch ladders. Remaining conditionals express actual
  widget state, data availability, eligibility, input and recovery; eliminating
  every conditional would obscure those responsibilities.
- The shared column picker serves 23 composition sites with independent policies,
  role groups, search, virtualization, ordering and bulk operations. Profiles
  retain numeric/non-numeric exclusivity; analysis and correlations retain their
  feature limits. The source column catalog has a separate responsibility:
  browsing schema and applying reversible interpretations.
- Shared viewport content supplies Auto/Expand/Restore/drag to plots and original
  text, tokens, images, arrays, audio and comparisons. Content retains its own
  axes, camera, zoom, pixel values, token spans and scoped selection.
- The shell has Source/Columns, Canvas, Context and Table. Standalone Analysis is
  removed; its unique controls, results, cluster centers/inertia and provenance
  live under Relationships context. Export captures a source binding in the File
  dialog. Gesture explanations use contextual help; data facts and diagnostics
  remain visible.

The larger composition modules (`shell/assembly.py`, `shell/page.py`,
`shell/inspect_assembly.py`) own explicit wiring and native lifetimes. The larger
file/editor controllers own coordination and file/session lifecycle, while
feature preparation and persistence serialization live in their own packages.
The 300-line review trigger does not justify splitting these cohesive orchestration
units merely to reduce their line counts.

## Data integrity and lifecycle

Pre-frame polling coordinates four shared bounded workers and publishes prepared
state. Table/profile preparation, file discovery, source fingerprints, media
loading, tokenizer work and analysis use workers. Native callbacks render bounded
rows, points, records and prepared payloads. Font loading and GPU uploads remain
native-thread responsibilities. Selection masks are bounded and revision-bound;
legend visibility is applied separately and never mutates cached masks.

File/view/revision identity is preserved through jobs, record mappings, selections,
comparisons and probes. Closing a file abandons publication into it; executing jobs
are not falsely described as stopped. Pending view completion does not steal
focus. Explicit Open result and source links perform navigation. Original cell
values and source files remain authoritative; mappings and interpretations do not
rewrite them. Failed transforms/imports remain transactional. Export refuses all
ready, attempted and recoverable source paths and retains its captured source
when active tabs change.

GUI owners release native textures before renderer shutdown. Reference previews
share bounded CPU/GPU retention; original-pixel and spectral owners are included
in the measured texture lifecycle. The media matrix tracks real native texture
owners and application RGBA payload, not physical driver VRAM. Resource gates use
actual retained process RSS where declared, and distinguish cold startup from
additional profiling allocation.

Versioned session v3, preferences v2 and layout v2 retain recipes, interpretations,
settings, selections, modality controls and current custom docking. Legacy layout
state resets with a notice. Default layouts adapt across sizes; customized docking
and splitter sizes survive. Restoring a session does not fit ML, train tokenizers
or begin playback. Missing/changed-source recovery preserves usable tabs.

## Capability coverage and scope limits

[gui-harness-audit.md](gui-harness-audit.md) and its per-harness manifest map retired
native harnesses to current native checks and behavioral tests. Domain engines and
all behavioral test modules remain; obsolete widget-patching harnesses are
recoverable from Git. Existing resource fixtures/budgets were migrated, including
operations, large/wide exploration, references, dense annotations, structured
objects, compressed arrays, CPU checkpoints, text, image profiles, comparisons,
analysis and multi-file closure.

The refactor principally replaces presentation and coordination. Polars import,
replayable operations, analysis implementations, structured/array adapters,
profiling/statistics, image/audio/text decoding and workspace recipe engines remain
in their established subsystems. Narrow fixes include selected-color invalidation,
cooperative exact character tokenization, selection-mask reuse and versioned
navigation/layout migration. This does not introduce a second table engine,
annotation editing, arbitrary Python mappings, model inference, an out-of-core
table engine or public release infrastructure.

Acceptance is Linux Mesa software OpenGL on this machine. Accelerated rendering
and other platforms remain unverified. Human audio listening remains explicitly
deferred, and the separate Titanic human usability gates remain open. Automated
refactor acceptance does not close those human follow-ups.

## Final verification

Final native inventory, full tests and installed-wheel verification are being
completed. Detailed final evidence will be recorded here before merge.
