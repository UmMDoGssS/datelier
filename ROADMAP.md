# Datelier delivery roadmap

## V1 definition and starting point

Datelier v1 is a Linux-first, local desktop workbench for memory-sized tabular
datasets. The target stack is Python 3.14+, Polars, and Dear ImGui/ImPlot through
[ImGui Bundle](https://github.com/pthom/imgui_bundle/blob/main/docs/book/core_libs/hello_imgui_immapp.md).
V1 combines immediate previews, bounded automatic exploration, reversible
transformations, on-demand PCA/t-SNE/UMAP/k-means, and customizable workspaces.

Supported v1 imports are CSV/TSV, JSON/JSONL, Parquet, and tabular XML. Export
targets are CSV and Parquet. Workspaces save source references and recipes,
not bundled data snapshots. ML requires an explicit command. Third-party
plugins, arbitrary Python mappings, additional platforms, larger-than-memory
table execution, images, text, and audio are outside the completed v1 baseline.
The requested editor and multimodal expansion now has concrete delivery gates
in [Phases 9–14](#authorized-editor-and-multimodal-expansion); other post-v1
directions remain optional investigations.

The repository has a Python 3.14+ `uv`-managed `src/` package, configured
Pyrefly/pytest/Ruff, and a locked application stack. Phase 0 is verified with
a synthetic docking/plot CLI probe, tiny analysis runs, and benchmark fixtures.
[Phase 0 evidence](docs/phase-0.md) records versions, commands, budgets, and
limitations, including the verified Mesa software renderer. Phase 1 now provides
CSV import, dataset identity/revisions, and a responsive
inspection workbench; [Phase 1 evidence](docs/phase-1.md) records its passed
gates. Phase 2 provides TSV, JSON/JSONL, Parquet, and configurable tabular XML
with explicit nested-input diagnostics; [Phase 2 evidence](docs/phase-2.md)
records its passed gates. Phase 3 provides reversible transformations and explicit
export; [Phase 3 evidence](docs/phase-3.md) records its passed gates. Phase 4
provides automatic exploration and linked selections;
[Phase 4 evidence](docs/phase-4.md) records its baseline gates, and
[richer-inspection evidence](docs/richer-inspection.md) records passed comparison,
color and matrix extensions. Phase 5 provides explicit analysis and linked 3D
views; [Phase 5 evidence](docs/phase-5.md) records its passed gates. Phase 6 provides referenced workspaces, saved layouts, themes and plot preferences;
[Phase 6 evidence](docs/phase-6.md) records its passed gates. Phase 7 passes
end-to-end hardening and local installation; [Phase 7 evidence](docs/phase-7.md)
records workflow/resource checks and the clean-wheel install. The personal-use
v1 scope is complete. Phase 8 remains optional investigation for concrete needs.
Phases 9–14 are the approved editor and multimodal sequence. Phase 9 passes
independent tabs/shared workers, Welcome/recent sources/editor controls,
whole-session persistence/recovery and cross-file comparisons. Phase 10 passes
richer interpretations, nearby lazy previews, conditional table presentation
and gallery/detail Inspect with direct media/text records;
[Phase 10 evidence](docs/phase-10.md) records correctness, native restoration and
measured resources. Phase 11 passes structured objects, lazy NumPy arrays,
confirmed record mappings and optional restricted CPU checkpoints;
[Phase 11 evidence](docs/phase-11.md) records restoration, resource and clean-install
acceptance. Phase 12 passes local tokenization/training, exact text profiles,
original token-span Inspect and shared-tokenizer cross-file comparisons;
[Phase 12 evidence](docs/phase-12.md) records native/restoration, resource and
clean-install acceptance. Phase 13 and later implementation gates remain open.
These gates do not change existing feature or usability acceptance.

A concrete post-v1 usability need is recorded in the
[Titanic UX review and proposed repair plan](docs/ux-titanic-review.md): readable
plot axes and sizes, unified inspection/analysis controls, and more direct
workflows. [Implementation evidence](docs/ux-implementation.md) records the
passed single-column chart step, contextual coordinate controls, and chart
sizing/axis repairs, with separately verified slices. Remaining
steps and user usability validation remain open. Existing feature gates are
unchanged.

The next requested plot-readability follow-up passes 3D viewing-face controls,
annotated correlation heatmaps with color scales, and named pair-grid axes.
[Implementation evidence](docs/ux-implementation.md#follow-up--3d-faces-and-relationship-readability-complete)
records live input/native-state checks and the full-suite gate for these slices.

This is a simple personal tool. Phase 7 verifies reliability and local setup;
public publishing, release automation and product infrastructure are not goals.

## Gate and evidence rules

- Follow [AGENTS.md](AGENTS.md): plan bounded steps, implement one, verify it,
  fix failures, review, and commit before starting the next step. Suggested
  commit sequences below are ordered slices, not permission to batch the work.
  Feature commits include their relevant tests; separate test commits expand
  coverage rather than postpone verification of earlier steps.
- All progress checkboxes start unchecked. Check milestone items as their
  deliverables, gates, evidence, and step commits are completed. A milestone is
  complete only after its exit gate passes with recorded verification evidence.
  Add **in progress** or **blocked** notes with the concrete dependency as needed;
  check a phase complete only after all its milestone exit gates pass.
- Phase entry requires the previous phase's exit plus milestone-specific
  prerequisites. Phase exit requires every milestone in that phase to pass.
  Phase 8 investigations are independent and optional; each requires the local
  v1 install gate and a concrete personal-use need. Phase 9 starts from M7.2 and
  the verified source package refactor, independently of Phase 8 completion;
  Phases 10–14 then follow their preceding phase's exit gates.
- Each code step requires Pyrefly, relevant tests, Ruff checks once established,
  and applicable GUI smoke checks. Each implementation milestone exit also
  requires the full test suite and its listed verification. Documentation-only
  steps use the document checks in AGENTS.md. Do not mark unavailable checks passed.
- Record evidence beside the milestone: commands and outcomes, relevant commit
  IDs, fixture names, manual GUI observations where applicable, and limitations.
  An implemented feature alone is insufficient evidence. Keep datasets out of
  commits except small synthetic or appropriately licensed fixtures.
- Use small deterministic fixtures for correctness and progressively larger
  benchmark tables, including roughly 10k, 100k, and 1m rows and a wide-table
  case. Record width, types, reference hardware, versions, wall time, and peak
  memory. One million rows is a test direction, not a universal capacity claim.
- Establish explicit preview, interaction, and memory acceptance budgets from
  the feasibility baseline; record them before judging later performance gates.
  Identify which jobs use sampling and resource limits rather than treating
  every algorithm as suitable for the largest table.
- Apply relevant edge-case gates throughout: empty/malformed input, mixed types,
  null/nonfinite values, high cardinality, wide tables, source preservation,
  operation replay, row alignment, stale results, and background-job failure.

## Phase 0 — Foundation and feasibility

- [x] **Phase complete.** **Entry:** existing scaffold. **Exit:** M0.1 and M0.2 pass. [Evidence](docs/phase-0.md) recorded 2026-10-04.

### M0.1 — Establish the development baseline

- [x] **Deliverables:** Python 3.14+ metadata, consistent lockfile, pytest/Ruff configuration, documented check commands.
- [x] **Entry gate:** inspect the scaffold and contributor conventions; confirm the available Python 3.14 environment.
- [x] **Exit gate:** clean environment sync and existing CLI launch work; Pyrefly, lint, format checks, and a meaningful baseline test pass.
- [x] **Verification evidence:** [baseline evidence](docs/phase-0.md#m01-development-baseline) records clean sync, Python 3.14.7, CLI launch, dev imports, and all check outcomes.
- [x] **Step commit:** `768a8c6` — `build: establish Python 3.14 development baseline` combines the metadata, tools, documentation, and installed-entry-point test as one verified foundation step.

### M0.2 — Validate stack integration and performance fixtures

- [x] **Deliverables:** Linux feasibility slice, verified dependency set, synthetic benchmark fixtures, recorded baseline and acceptance budgets.
- [x] **Entry gate:** M0.1 passes; the GUI can be exercised on a Linux graphical environment using Mesa software OpenGL.
- [x] **Exit gate:** docking and an ImPlot plot render; selected Polars data reaches the plot; tiny PCA, t-SNE, UMAP, and k-means runs succeed on Python 3.14.7.
- [x] **Verification evidence:** [complete evidence](docs/phase-0.md) includes locked versions, screenshots/dock IDs, finite algorithm shapes and row alignment, 12 fresh-process table measurements, large/wide GUI timings, and acceptance budgets. Full suite: 17 passed; Pyrefly/Ruff/lock consistency checks pass. Accelerated rendering remains unverified; only software rendering is claimed.
- [x] **Step commits:** `97f2f08` dependencies → `fe81f8b` GUI/table integration → `a2c737c` analysis compatibility → `1e4cc32` measured baseline and bounded scatter rendering.

## Phase 1 — First usable inspection slice

- [x] **Phase complete.** **Entry:** Phase 0 passes. **Exit:** M1.1 and M1.2 pass. [Evidence](docs/phase-1.md) recorded 2026-10-04.

### M1.1 — CSV import and dataset state

- [x] **Deliverables:** CSV adapter, import options/diagnostics, typed dataset state, stable row identity, dataset revisions.
- [x] **Entry gate:** stack feasibility passes and Polars import behavior is verified.
- [x] **Exit gate:** normal CSV files load correctly; empty, malformed, and mixed-type inputs have defined outcomes; row identity is independent of display order.
- [x] **Verification evidence:** [M1.1 evidence](docs/phase-1.md#m11-csv-import-and-dataset-state): 22 focused tests, 39 full-suite tests, Pyrefly/Ruff and source preservation checks pass.
- [x] **Step commits:** `cd69ef1` dataset identity/revisions → `7c65f4f` CSV import/options/diagnostics, including failure and preservation tests.

### M1.2 — Responsive preview and job lifecycle

- [x] **Deliverables:** virtualized table, schema/null summaries, background loading, visible job status, revision-aware completion handling.
- [x] **Entry gate:** M1.1 passes and the import contract supplies data, metadata, and errors without GUI dependencies.
- [x] **Exit gate:** loading does not block rendering; the preview shows correct rows/types; failures surface; changing datasets prevents an older job from replacing active state.
- [x] **Verification evidence:** [M1.2 evidence](docs/phase-1.md#m12-responsive-preview-and-job-lifecycle): 48 full-suite tests, Pyrefly/Ruff, live-reload/rapid-switch/failure/wheel GUI checks, and 12 fresh-process measurements pass. Large/wide frame p95 is 12.41/12.98 ms; recorded loading and memory budgets pass.
- [x] **Step commits:** `c717b5c` background loading/preparation → `2609a9e` virtualized preview/schema/status → `31bdccd` lifecycle and performance acceptance evidence.

## Phase 2 — Format coverage

- [x] **Phase complete.** **Entry:** Phase 1 passes. **Exit:** M2.1 and M2.2 pass. [Evidence](docs/phase-2.md) recorded 2026-10-04.

### M2.1 — TSV, JSON/JSONL, and Parquet

- [x] **Deliverables:** adapters/options for remaining straightforward formats, sharing dataset state, preview, and diagnostics.
- [x] **Entry gate:** the CSV inspection slice and importer contract pass their gates.
- [x] **Exit gate:** each format loads equivalent tabular fixtures with appropriate types; malformed/unsupported structures produce actionable diagnostics without corrupting active state.
- [x] **Verification evidence:** [M2.1 evidence](docs/phase-2.md#m21-tsv-jsonjsonl-and-parquet): 92 full-suite tests, cross-format schemas/values/nulls/identity, strict failure cases, Pyrefly/Ruff, and five import-to-preview/diagnostic GUI checks pass.
- [x] **Step commits:** `5e566c6` shared contract/TSV → `a012e2c` JSON/JSONL → `4bc824b` Parquet; acceptance evidence follows in the M2.1 gate commit.

### M2.2 — Tabular XML and nested-input handling

- [x] **Deliverables:** XML adapter, configurable record extraction, explicit nested-data handling, parse/type diagnostics.
- [x] **Entry gate:** M2.1 passes and format options/errors use the shared importer interface.
- [x] **Exit gate:** repeated XML records become a correct table; extraction settings are visible; nested XML/JSON is explicitly mapped or clearly rejected rather than silently losing data.
- [x] **Verification evidence:** [M2.2 and final phase evidence](docs/phase-2.md#m22-tabular-xml-and-nested-input-handling): 151 tests, XML extraction/type/nesting fixtures, all-format state/source preservation, seven diagnostic/settings GUI runs, ten large/wide live GUI gates, and 20 fresh-process format measurements pass. Pyrefly/Ruff and lock checks pass.
- [x] **Step commits:** `81d8a0d` XML/extraction controls → `f7fbf34` input/state safety → `4ee9023` parser memory → `589f5bb` live responsiveness → `130c320` format-neutral guidance → `1eb6737` XML literals → `e54c431` literal column names → `7a811b6` temporal preview precision; final acceptance evidence follows in the Phase 2 gate commit.

## Phase 3 — Reversible transformations

- [x] **Phase complete.** **Entry:** Phase 2 passes. **Exit:** M3.1 and M3.2 pass. [Evidence](docs/phase-3.md) recorded 2026-10-04.

### M3.1 — Ordered operations and undo/redo

- [x] **Deliverables:** replayable pipeline, sorting, filtering, column selection, undo/redo controls, revision changes.
- [x] **Entry gate:** stable row identity and revision-aware dataset/job state are established.
- [x] **Exit gate:** operation order is respected; undo/redo restores expected tables; new edits handle redo history consistently; failures leave the active pipeline intact.
- [x] **Verification evidence:** [M3.1 evidence](docs/phase-3.md#m31-ordered-operations-and-undoredo): 159 full-suite tests, Pyrefly/Ruff, and eight live GUI history/identity/preview checks pass.
- [x] **Step commits:** `eb62f92` replayable operations/history → `49a3051` background editing and GUI undo/redo.

### M3.2 — Mapping, derived columns, and export

- [x] **Deliverables:** casts, missing-value operations, lookup mappings, constrained expressions, derived columns, explicit CSV/Parquet export.
- [x] **Entry gate:** M3.1 passes with deterministic replay and tested operation failure behavior.
- [x] **Exit gate:** transformations replay correctly with type/null diagnostics; expressions cannot execute arbitrary Python; exported tables match the active result and source files remain unchanged.
- [x] **Verification evidence:** [M3.2 and final evidence](docs/phase-3.md#m32-mapping-derived-columns-and-export): 222 tests, all-format transformation/replay/export workflows, strict expression rejection, source/identity invariants, GUI transform/export gates, and four fresh-process plus two live large/wide benchmarks pass. Pyrefly/Ruff/lock checks pass.
- [x] **Step commits:** `e00940a` typed transforms → `7f99783` constrained expressions → `1a9f991` atomic export → `9a62fcd` diagnostics/temporal filters → `bc76f68` completed nanosecond fix → `a411d22` workflow/resource acceptance.

## Phase 4 — Automatic and interactive exploration

- [x] **Phase complete.** **Entry:** Phase 3 passes. **Exit:** M4.1 and M4.2 pass. [Evidence](docs/phase-4.md) recorded 2026-10-04.

### M4.1 — Type-aware profiles and automatic plots

- [x] **Deliverables:** numeric/categorical/temporal profiles, distributions, counts, correlations, bounded suggested scatter plots, revision-aware prepared plot data.
- [x] **Entry gate:** table operations and revision invalidation are tested; baseline summaries and background jobs work.
- [x] **Exit gate:** opening a dataset automatically provides the exploration dashboard; plots match known data; unsuitable columns and excessive pairwise work are handled explicitly.
- [x] **Verification evidence:** [M4.1 evidence](docs/phase-4.md#m41-type-aware-profiles-and-automatic-plots): 230 full-suite tests, Pyrefly/Ruff, known distributions/correlations, bounded high-cardinality/wide work, and live dashboard/edit-invalidation checks pass.
- [x] **Step commits:** `345a45e` profiles → `4b144cb` prepared plots/background lifecycle → `8bc4d29` automatic dashboard.

### M4.2 — Plot controls and linked selection

- [x] **Deliverables:** column/plot controls, zoom/pan, linked table/plot selection, sampling labels, configurable bounded expansion.
- [x] **Entry gate:** M4.1 passes and plot data carries correct row identity and revision metadata.
- [x] **Exit gate:** interactions select the correct rows after sort/filter/sample operations; sampling/truncation is visible; wide tables and interaction timings meet recorded limits.
- [x] **Verification evidence:** [M4.2 and final evidence](docs/phase-4.md#m42-plot-controls-and-linked-selection): 242 tests, Pyrefly/Ruff, all-format exploration/selection workflows, stale-result checks, live gesture/settings checks, four fresh-process benchmarks, and large/wide live GUI gates pass. Frame p95 is 17.51/17.73 ms; peak RSS is 679.21/622.70 MiB.
- [x] **Step commits:** `8f9df0a` configurable plots and linked selections → `7cfb81f` bounded rendering, precision fixes, and workflow/resource acceptance.

### M4.3 — Richer inspection extension

- [x] **Deliverables:** multi-column histogram/KDE/ECDF/box/violin comparisons, independent scatter axes and column colors, Pearson heatmap and bounded pair grid.
- [x] **Exit gate:** comparison/statistics/identity tests, live mode/navigation/selection checks, and existing inspection resource budgets pass.
- [x] **Verification evidence:** [incremental and final evidence](docs/richer-inspection.md): 271 tests, Pyrefly/Ruff/lock checks, live modes/navigation/recovery, four fresh headless fixtures and eight large/wide GUI cases pass the 33ms/1GiB budgets.

## Phase 5 — On-demand unsupervised analysis

- [x] **Phase complete.** **Entry:** Phase 4 passes. **Exit:** M5.1, M5.2 and M5.3 pass. [Evidence](docs/phase-5.md) recorded 2026-10-04.

K-means is the current clustering method. Spectral, agglomerative, DBSCAN and
HDBSCAN remain future additions; this phase introduces no public registry or
workspace persistence schema.

### M5.1 — Shared analysis flow, PCA, and k-means

- [x] **Deliverables:** explicit feature/preprocessing controls, analysis job/result state, PCA and k-means, parameters/seeds and input provenance.
- [x] **Entry gate:** background jobs, revision invalidation, and linked selections pass; algorithm dependencies passed M0.2.
- [x] **Exit gate:** only an explicit command starts analysis; unsuitable inputs have diagnostics; results record preprocessing/settings and align with included source rows.
- [x] **Verification evidence:** [M5.1 evidence](docs/phase-5.md): 264 full-suite tests, zero Pyrefly errors, Ruff, all-format analysis workflows, live raw/reduced cluster-color checks, and eight bounded fresh-parent/worker resource runs pass.
- [x] **Suggested step commits:** `feat: configure analysis inputs` → `feat: run pca analysis` → `feat: run k-means clustering` → `feat: inspect analysis provenance`.

### M5.2 — t-SNE, UMAP, and bounded jobs

- [x] **Deliverables:** t-SNE/UMAP controls and plots, parameter validation, progress where available, cancellation/safe abandonment, explicit resource limits.
- [x] **Entry gate:** M5.1 passes and the common analysis flow handles preprocessing, identity, provenance, and failure.
- [x] **Exit gate:** both algorithms run on eligible data by command; invalid parameters are rejected; abandoned/stale jobs cannot publish results; large inputs use visible limits or sampling.
- [x] **Verification evidence:** [M5.2 evidence](docs/phase-5.md#m52--t-sne-umap-and-bounded-jobs): 267 full-suite tests, Pyrefly/Ruff, finite aligned 2/3D embeddings, seed behavior, actual worker cancellation, live t-SNE/UMAP linked-color workflows, and eight resource cases pass.
- [x] **Suggested step commits:** `feat: add t-sne analysis` → `feat: add umap analysis` → `feat: bound and abandon analysis jobs`.

### M5.3 — 3D views and final exploration acceptance

- [x] **Deliverables:** raw XYZ and three-component embedding plots, column/cluster colors, linked projected picking/brushing and camera gestures.
- [x] **Exit gate:** 3D source identity, renderer/gesture checks and final inspection/analysis resource gates pass; evidence recorded.
- [x] **Verification evidence:** [M5.3 evidence](docs/phase-5.md#m53--3d-and-final-live-acceptance): 271 tests, Pyrefly/Ruff/lock checks, live 3D gestures and explicit three-component workflows, visible-marker checks, large/wide GUI frame/memory gates, live combined worker budgets and recorded cancellation timing pass.

## Phase 6 — Workspaces and customization

- [x] **Phase complete.** **Entry:** Phase 5 passes. **Exit:** M6.1 and M6.2 pass. [Evidence](docs/phase-6.md) recorded 2026-10-04.

### M6.1 — Referenced-source workspace persistence

- [x] **Deliverables:** versioned workspace files with source references, import options, operation recipes, analysis settings, and views; source detection/relinking.
- [x] **Entry gate:** operations, plot configuration, and analysis settings have typed representations and reproducible behavior.
- [x] **Exit gate:** save/reopen restores the intended workspace; missing/changed sources are detected; relinking works; loading settings does not automatically rerun ML.
- [x] **Verification evidence:** [M6.1 evidence](docs/phase-6.md#m61--referenced-source-workspace-persistence): 312 full-suite tests, Pyrefly/Ruff, strict recipe/source/replay/job tests and live save/restart/relink/redo/selection checks pass; no implicit ML.
- [x] **Step commits:** `3e5464c` versioned recipes → `7d9d494` background restore/relink → `2b513b4` GUI controls, CLI and M6.1 acceptance evidence.

### M6.2 — Saved layouts, themes, and plot preferences

- [x] **Deliverables:** dock layout persistence, configurable themes, saved plot preferences, usable restoration controls.
- [x] **Entry gate:** M6.1 passes and docking/plot controls are already functional.
- [x] **Exit gate:** layout/theme/preferences persist across restart; workspace restoration preserves valid views; unusable layouts can be reset without losing dataset recipes.
- [x] **Verification evidence:** [M6.2 evidence](docs/phase-6.md#m62--saved-layouts-themes-and-plot-preferences): 333 full-suite tests, Pyrefly/Ruff, independent preference recovery, three fresh-process rearrange/restart/default/reset/restore GUI checks and linked-selection/gesture regressions pass.
- [x] **Step commit:** `29ce51e` — dock layout module, versioned preference storage, theme/menu/default restoration, fresh-process GUI gate and final evidence form one verified customization step.

## Phase 7 — Personal-use hardening and installation

- [x] **Phase complete.** **Entry:** Phases 0–6 pass. **Exit:** M7.1 and M7.2 pass. [Evidence](docs/phase-7.md) recorded 2026-10-04.

### M7.1 — End-to-end correctness and performance

- [x] **Deliverables:** complete workflow coverage, pathological-input regression cases, measured performance against documented budgets.
- [x] **Entry gate:** every v1 capability has passed its milestone; benchmark environment, fixtures, budgets, and algorithm limits are recorded.
- [x] **Exit gate:** import → inspect → transform → plot → analyze → save/reopen → export workflows pass; pathological data and job failures are handled; measured budgets pass.
- [x] **Verification evidence:** [M7.1 evidence](docs/phase-7.md#m71--complete-workflows-and-reliability): 344 tests, Pyrefly/Ruff, six format GUI regressions, fresh save/reopen workflow, 40 headless resource runs and large/wide live analysis pass. Abrupt worker exits now report their exit code and allow retry.
- [x] **Step commits:** `3e946d1` complete workflow tests → `1ff0298` worker-exit error detail → `e11158e` fresh-process GUI walkthrough and recorded acceptance evidence.

### M7.2 — Local Linux installation

- [x] **Deliverables:** locally installable wheel/source archive, working CLI launch, concise setup/usage documentation and personal-use checklist.
- [x] **Entry gate:** M7.1 passes and no earlier required v1 gate remains open.
- [x] **Exit gate:** a clean Linux environment can install and launch the built package and complete a representative workflow using the documentation; package version/metadata and checklist are consistent.
- [x] **Verification evidence:** [M7.2 evidence](docs/phase-7.md#m72--local-linux-installation): built wheel/source archive, isolated runtime install with locked dependencies, all CLI launch modes, fresh-process installed GUI workflow, metadata/hash checks and README walkthrough pass. Version 0.1.0 retained; nothing published.
- [x] **Step commits:** `b6d201d` personal installation/first-session documentation → final local-package acceptance evidence and checklist recorded with this gate.

## Phase 8 — Post-v1 investigations

- [ ] **Phase complete.** **Entry:** M7.2 passes. **Exit:** each pursued investigation has evidence and an approved specification; unpursued directions remain unchecked.

These milestones produce proposals, not v1 commitments or permission to build
an undefined feature. Investigate each direction separately and define its
implementation milestones only after its specification is approved.

The requested format, image, and text workflows now have an approved delivery
sequence in [Phases 9–14](#authorized-editor-and-multimodal-expansion). M8.2,
M8.5, and M8.6 remain historical investigation entries with their existing
unchecked evidence gates; they do not require duplicate proposals or another
approval before the concrete milestones below can begin. Platform, general
out-of-core table execution, and public extension directions remain optional.

### M8.1 — Windows/macOS distribution

- [ ] **Deliverables:** platform compatibility and packaging proposals for Windows and macOS, assessed separately.
- [ ] **Entry gate:** M7.2 passes; target-platform test environments are available.
- [ ] **Exit gate:** each proposed platform has verified GUI/dependency feasibility and an approved support, packaging, and acceptance specification.
- [ ] **Verification evidence:** installation/launch smoke results, platform-specific issues, supported interpreter/architecture findings, and proposal decisions.
- [ ] **Suggested step commits:** `docs: assess windows distribution` → `docs: assess macos distribution` → `docs: specify platform rollout`.

### M8.2 — Additional data formats

The requested structured JSON/TOML and NPY/NPZ/PyTorch inputs are specified in
[Phase 11](#phase-11--structured-objects-arrays-and-checkpoints). Further formats
still require a concrete need.

- [ ] **Deliverables:** evidence-backed priorities and importer proposals for formats beyond v1.
- [ ] **Entry gate:** M7.2 passes and concrete format/use-case requests exist.
- [ ] **Exit gate:** each selected format has representative fixtures, a table-mapping/dependency assessment, and an approved import/export and acceptance specification.
- [ ] **Verification evidence:** fixture findings, adapter feasibility, round-trip limitations, and proposal decisions.
- [ ] **Suggested step commits:** `docs: assess requested data formats` → `docs: specify additional import support`.

### M8.3 — Larger-than-memory execution

- [ ] **Deliverables:** measured limits and a proposal for lazy/out-of-core execution.
- [ ] **Entry gate:** M7.2 passes and v1 benchmarks identify concrete memory/capacity constraints.
- [ ] **Exit gate:** an approved specification states supported operations, preview/plot/analysis constraints, storage approach, and measurable resource targets.
- [ ] **Verification evidence:** memory/query feasibility measurements, conversion/copy costs, operation compatibility findings, and proposal decisions.
- [ ] **Suggested step commits:** `perf: measure larger-table constraints` → `docs: specify out-of-core execution`.

### M8.4 — Extension hooks

- [ ] **Deliverables:** concrete extension use cases and a proposal for importer, transform, plot, or analysis hooks.
- [ ] **Entry gate:** M7.2 passes and actual extension requirements justify a public boundary.
- [ ] **Exit gate:** an approved specification defines required hooks, compatibility/lifecycle expectations, typing, execution behavior, and acceptance cases without speculative APIs.
- [ ] **Verification evidence:** use-case inventory, existing-boundary assessment, compatibility tradeoffs, and proposal decisions.
- [ ] **Suggested step commits:** `docs: assess extension requirements` → `docs: specify extension boundaries`.

### M8.5 — Image inspection

The requested image/heatmap and detection-box workflows are specified in
[Phase 13](#phase-13--images-heatmaps-and-detection-annotations), using Phase 10's
lazy preview and record-inspection foundation.

- [ ] **Deliverables:** image-dataset inspection proposal grounded in representative analyst workflows.
- [ ] **Entry gate:** M7.2 passes and concrete image use cases and representative data are available.
- [ ] **Exit gate:** an approved specification defines input/data identity, previews, inspection interactions, analysis scope, resource constraints, and delivery gates.
- [ ] **Verification evidence:** dataset/workflow findings, preview and storage feasibility, reuse of workbench components, and proposal decisions.
- [ ] **Suggested step commits:** `docs: investigate image inspection` → `docs: specify image workbench milestones`.

### M8.6 — Text inspection

The requested tokenization, statistics, and token-span inspection are specified
in [Phase 12](#phase-12--text-profiling-and-token-inspection).

- [ ] **Deliverables:** text-dataset inspection proposal grounded in representative analyst workflows.
- [ ] **Entry gate:** M7.2 passes and concrete text use cases and representative data are available.
- [ ] **Exit gate:** an approved specification defines records/encoding, previews, inspection interactions, analysis scope, resource constraints, and delivery gates.
- [ ] **Verification evidence:** dataset/workflow findings, encoding and preview feasibility, reuse of workbench components, and proposal decisions.
- [ ] **Suggested step commits:** `docs: investigate text inspection` → `docs: specify text workbench milestones`.

## Authorized unsupervised inspection expansion

The concrete user request adds clustering and embedding choices beyond the
completed v1 baseline, with exclusive Uniform/Column/method Colors sources.
[Delivery gates and verification](docs/unsupervised-methods.md) record completion:
26 methods, 439 passing tests, all-method Titanic GUI acceptance, saved recipes
and bounded-worker resource/cancellation checks. This work uses the existing
analysis worker and dependencies; loading or
restoring a workspace must still never launch ML automatically.

## Authorized categorical inspection follow-up

The user requested a broader Relationships tab, category charts, inferred Text
and Identifier roles with overrides, and selectable correlation-grid diagonals.
[Delivery gates](docs/categorical-inspection.md) record all three verified
steps: reversible roles, category charts and selectable grid diagonals, with
457 passing tests and native Titanic/workspace compatibility checks. Original Titanic UX gates remain
separate and open where their evidence is incomplete.

## Authorized Schema and profile comparison follow-up

The user requested explicit Schema counts and shape, numeric statistics below
plots, and an exclusive category/multiple numeric profile checklist. Deliver
the three bounded steps and record evidence in
[Schema and profile comparison gates](docs/profile-comparison.md). All three
steps are verified: Schema counts/shape, worker-prepared statistics tables, and
the exclusive category/multiple numeric checklist with saved selections.

## Authorized category distribution clarification

Category–numeric Relationships now require box/violin plots; grouped bars stay
for category–category comparisons, and single-column counts belong in Profiles.
[Delivery gates](docs/category-distribution-follow-up.md) cover worker preparation
followed by native UI and saved-view routing. Both steps are verified, including
linked selections, compatible inputs, saved-view migration and reopen behavior.

## Authorized scatter views and native legends

The user requested separate 2D/3D scatter charts with matching reduction output,
axis selectors beneath Coordinates, and native legends across inspection plots.
[Delivery gates](docs/scatter-views-and-legends.md) sequence scatter controls and
saved views before the all-plot legend audit and native verification.
Both steps are verified: independent scatter choices/heights and fixed component
counts, nested raw axes, native category/cluster legends and continuous scales,
visibility-aware linked interactions, saved-view compatibility, full tests and
native Titanic inspection. Original Titanic usability gates remain separate.

## Authorized source package refactor

Group source files by subsystem, with GUI rendering in a separate package.
Simplify redundant filename prefixes and update imports directly, without root
compatibility modules. Preserve behavior, CLI commands, class names, recipe
identifiers, dependencies and workspace schemas. Tests and smoke scripts retain
their current folder organization. `datelier:main` remains the CLI entry point;
package initializers stay minimal and imports name concrete modules.

| Package | Responsibilities |
| --- | --- |
| `core` | Dataset identity, column roles, scalars, sampling |
| `io` | Import adapters/contracts, parsing, loading, export |
| `pipeline` | Operations, history, editing, transforms, expressions |
| `inspection` | Table previews, profiles/statistics, profile selection, exploration |
| `plotting` | Prepared charts, distributions, relationships, colors, projection, selection |
| `analysis` | Algorithms/parameters, inputs, workers, provenance, analysis plots, cluster colors |
| `workspace` | Types, storage, recipes, restoration, preferences |
| `gui` | Application assembly, rendering, controls |
| `feasibility` | Existing organized feasibility probes |

GUI subpackages are `analysis`, `data`, `plots`, `profiles`, `workspace`, and
`widgets`; assembly, exploration orchestration, and layout sit directly in `gui`.
Use `analysis/runner.py` for dispatch, `analysis/cluster_colors.py` for the existing
cluster-color helpers, `pipeline/history.py` for history, `inspection/table.py`
for table preparation, `plotting/data.py` for plot preparation, and
`workspace/storage.py` for storage. GUI assembly becomes `gui/app.py`, the analysis
session `gui/analysis/session.py`, and the profile view `gui/profiles/view.py`.

### Bounded steps and acceptance gates

Verify, review and commit each step before starting the next. At every move,
update source/test/script imports, monkeypatch targets and source links.

- [x] Document the convention, target layout and open acceptance gates.
- [x] Move foundation, import/export and pipeline modules; focused tests,
  Pyrefly and Ruff pass.
- [x] Move inspection and plotting preparation; focused tests, Pyrefly and Ruff
  pass.
- [x] Move analysis; spawned publication, cancellation and stale-result checks,
  focused tests, Pyrefly and Ruff pass.
- [x] Move workspace persistence/preferences; round-trip and restore/relink
  checks, focused tests, Pyrefly and Ruff pass.
- [x] Organize GUI; existing workflow, workspace and scatter Mesa smoke checks
  pass alongside focused tests, Pyrefly and Ruff.
- [x] Final acceptance: full suite, wheel build, isolated installed CLI/workflow,
  stale-import/source-link audit and diff review pass with recorded evidence.

### Verification evidence

Planning baseline: all 94 non-bootstrap root modules have a subsystem assignment;
the existing `feasibility` package stays intact. The existing suite collects
493 tests. All package-refactor acceptance gates now pass; unrelated
feature and usability gates retain their existing status.

Step 1 (2026-10-05): convention and refactor sequence reviewed; local Markdown
links in `AGENTS.md`/`ROADMAP.md` and `git diff --check` pass. No application code
changed, so application checks are not required for this documentation step.

Step 2 (2026-10-05): 23 modules moved into `core`, `io`, and `pipeline`.
`uv run pytest` with dataset/column-role, all `test_import_*.py`, loading,
transforms, expressions, pipeline, editing, exporting and transformation-workflow
tests: **205 passed**. `uv run pyrefly check`: zero errors; `uv run ruff check .`
and `uv run ruff format --check .` pass. A relocation audit compares all 189
original Python modules with commit `c5e1add`, ignoring imports: non-import ASTs
are identical. Local links across all 19 Markdown documents and diff whitespace
pass. Verification uses `UV_CACHE_DIR=/tmp/datelier-uv-cache`, offline/no-sync uv
runs, and the existing thread limits for Polars/BLAS with a temporary Numba cache.

Step 3 (2026-10-05): 16 modules moved into `inspection` and `plotting`.
`uv run pytest` with preview, profiling/profile, distribution, exploration,
category, relationship, plot-data, coloring, selection, scatter3d and
complete-workflow tests: **100 passed**. Pyrefly zero errors, Ruff lint/format,
all 19 documents' local links and diff whitespace pass. Non-import ASTs of all
189 original Python modules remain identical; monkeypatch imports now target
the relocated modules. Step 2 commit: `a1f2883`; convention commit: `c5e1add`.

Step 4 (2026-10-05): 15 analysis modules grouped under `analysis`, including
the concrete `runner` and `cluster_colors` modules. `uv run pytest` with
`test_analysis_*.py`, plot-color-series, exploration-workflow and scatter-view
tests: **103 passed**, including real spawned workers, cancellation, abrupt
worker exit/retry and revision invalidation. Pyrefly zero errors, Ruff
lint/format, local links, non-import AST comparison and diff whitespace pass.
Step 3 commit: `ff04fb6`.

Step 5 (2026-10-05): six modules moved into `workspace`. `uv run pytest` with
`test_workspace*.py`, preferences, complete-workflow, scatter-view and
category-distribution tests: **92 passed**, covering recipe round trips,
missing/changed sources, relinking, failed/stale background restoration and
view settings. Pyrefly zero errors, Ruff lint/format, local links, unchanged
non-import ASTs and diff whitespace pass. Step 4 commit: `87e3376`.

Step 6 and final acceptance (2026-10-05): all 34 GUI modules moved into the
agreed subpackages. The package root now contains only `__init__.py` bootstrap
code; all new package initializers contain docstrings only. `uv run pytest` with
CLI, axis-control, scatter-view/scatter3d, selection, workspace-GUI-state,
profile-selection and plot-color-series tests: **57 passed**. Full
`uv run pytest`: **493 passed in 16.29s**. Pyrefly zero errors, Ruff lint/format,
all 19 Markdown documents' local links, stale-import audit and diff whitespace
pass. All 100 original application modules retain identical non-import ASTs,
as do 88 original test/script modules. Dependency metadata is unchanged.
Step 5 commit: `c5e4711`.

The existing workflow smoke failed its restored-selection assertion against
both the pre-refactor snapshot `c5e1add` and the reorganized source: it expected
a saved PCA coordinate source to render without fitting. Its verification setup
now asserts the saved PCA choice and explicitly switches to raw columns before
checking linked selection; restore still starts no ML. No application behavior
changed. The corrected workflow, workspace restore/relink and scatter-controls
smoke checks all pass with desktop display access and Mesa software OpenGL.
The sandbox could not open display `:0`; desktop checks ran outside that sandbox.
The rendered scatter screenshot was visually inspected.

`uv build --offline` builds the source archive and wheel. Wheel inspection finds
all **114** source Python modules, the unchanged `datelier:main` entry point and
no bytecode. An empty `/tmp/datelier-refactor-install` environment installs the
15 locked runtime dependencies and wheel; `uv pip check` validates all 16
packages, with pytest absent. From `/tmp`, installed imports resolve inside that
environment, CLI help passes, and default/feasibility CLI windows each render
20 frames (18 feasibility plot frames). The copied installed workflow passes
fresh save/reopen processes, explicit PCA/k-means, linked selection, both exports,
source preservation and no implicit ML on restore. Source save/reopen frame p95
is 14.37/12.99ms; installed p95 is 13.76/12.69ms, within existing smoke budgets.

[Machine-readable verification](docs/evidence/source-package-refactor.json)
records workflow/resource results, the baseline smoke correction and wheel hash.
Reproduction commands, with the uv/Numba caches and thread limits noted above:

```sh
export UV_CACHE_DIR=/tmp/datelier-uv-cache NUMBA_CACHE_DIR=/tmp/datelier-numba-cache
export POLARS_MAX_THREADS=8 OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1
uv run --offline --no-sync pytest
uv run --offline --no-sync pyrefly check
uv run --offline --no-sync ruff check .
uv run --offline --no-sync ruff format --check .
LIBGL_ALWAYS_SOFTWARE=1 uv run --offline --no-sync scripts/workflow_smoke.py --output /tmp/datelier-refactor-workflow.json
LIBGL_ALWAYS_SOFTWARE=1 uv run --offline --no-sync scripts/workspace_smoke.py
LIBGL_ALWAYS_SOFTWARE=1 uv run --offline --no-sync scripts/scatter_modes_smoke.py --output /tmp/datelier-refactor-scatter.ppm
uv build --offline
UV_PROJECT_ENVIRONMENT=/tmp/datelier-refactor-install uv sync --offline --locked --no-dev --no-install-project
uv pip install --offline --no-deps --python /tmp/datelier-refactor-install/bin/python dist/datelier-0.1.0-py3-none-any.whl
uv pip check --python /tmp/datelier-refactor-install/bin/python
cp scripts/workflow_smoke.py /tmp/datelier-refactor-installed-workflow.py
cd /tmp
LIBGL_ALWAYS_SOFTWARE=1 /tmp/datelier-refactor-install/bin/python /tmp/datelier-refactor-installed-workflow.py --output /tmp/datelier-refactor-installed-workflow.json
/tmp/datelier-refactor-install/bin/datelier --help
LIBGL_ALWAYS_SOFTWARE=1 /tmp/datelier-refactor-install/bin/datelier --smoke-frames 20
LIBGL_ALWAYS_SOFTWARE=1 /tmp/datelier-refactor-install/bin/datelier --feasibility --smoke-frames 20
```

## Authorized editor and multimodal expansion

The user approved the following six delivery phases after choosing independent
file tabs with cross-file comparisons, whole-session workspaces, checkpoint
inspection, nearby-folder discovery, local tokenizer import/training, direct
media files/folders, explicit expensive collection analysis, confirmable array
mappings, and annotation inspection/comparison. This extends the personal Linux
workbench beyond v1. It does not authorize model construction/inference,
annotation editing, a general out-of-core table engine, public plugins, or
additional platform support.

The immediate roadmap/contributor-guide update is documentation only. The
milestones below require implementation, verification, evidence, and coherent
step commits before any checkbox is checked. Each suggested commit sequence is
a set of bounded slices to verify individually under AGENTS.md.

### Shared contracts and defaults

- **File sessions and record views:** an application session owns independent
  file sessions, each with source identity, revisions, operations, selections,
  analysis settings, and views. Object/array files can contain named record
  views within their file tab. Keep Polars authoritative for tabular records and
  supporting columns; reference media/array payloads through typed adapters.
- **Identity and publication:** namespace source-record identity by file/view.
  Tag jobs/results with that identity, revision, settings, and source identity.
  Closing or superseding a view rejects its late results; numeric row IDs from
  different files must never share a selection accidentally.
- **Lazy preparation:** show source metadata and the initial table/object/array
  browser before expensive work. Resolve references, decode visible previews,
  and prepare selected profiles outside frame callbacks. Whole-collection
  text/media analysis, tokenizer training, and playback require explicit actions.
  Existing automatic basic tabular exploration remains available.
- **Resources:** use a shared bounded scheduler rather than multiplying worker
  pools per tab. Prioritize visible records and selected views, with configurable
  byte-bounded CPU/GPU caches and managed temporary storage. Eviction changes
  retained data, not available features. Prefer chunking or slower background
  computation when a complete result exceeds a preview/cache budget; label
  sampling and approximation and retain an exact-analysis action.
- **Interpretation and preservation:** retain physical types and original
  values. Explain inferred roles and keep overrides replayable, undoable, and
  saved. Reference discovery does not rewrite cells. Changing display scales,
  tokenization, or image normalization must not silently modify source data.
- **Startup and persistence:** startup and New Tab show Welcome; reopening an
  already-open source focuses its tab. Save references and recipes, including
  tokenizer artifacts, without bundling media, decompressed caches, or fitted
  ML results. Restoring opens metadata without training or playback.
- **Chosen presentation defaults:** text folders use one document per file,
  with an explicit line-record option. Numeric shading uses a percentile scale
  with marked extremes and a selectable linear min/max scale. Comparisons map
  fields explicitly per file, share bins/category ordering, and expose count
  versus density normalization; selections remain associated with their source.

### Verification requirements for Phases 9–14

- Verify Python 3.14/Linux dependency feasibility before the owning subsystem:
  Pillow for image decoding; Hugging Face Tokenizers for BPE/Unigram;
  SoundFile/SoundDevice/SciPy for audio; CPU PyTorch as an explicit installation
  extra. Verify system decoder/playback requirements in the clean-install gate.
  Add dependencies with uv and keep the lockfile consistent; preserve existing
  GUI/Polars boundaries and isolate untyped dependency APIs.
- Every code step requires Pyrefly, focused behavioral tests, Ruff lint/format,
  applicable native GUI smoke checks, diff review, and a step commit. Every
  milestone exit also requires the full suite and its listed acceptance cases.
  Record commands, versions, fixture details, observations, and material limits
  before marking gates passed. Documentation-only slices use document checks.
- Include duplicate filenames/stems, empty/malformed sources, missing/changed
  assets, mismatched arrays, null/nonfinite values, incompatible interpretations,
  cross-file row-ID collisions, stale jobs, and closure during background work.
  Verify source preservation and workspace migration/recovery throughout.
- Preserve existing single-table responsiveness/resource gates, including the
  recorded 33 ms frame-p95 target. Establish fixture-specific multimodal and
  multi-file budgets before judging their acceptance: metadata/first-preview
  latency, selected-profile latency, frame p95, CPU/GPU cache retention, peak
  memory, temporary-disk use, and cleanup after switching/closing views. Longer
  background calculations are acceptable when capability remains accessible;
  unmeasured dependency or performance gates remain open.

Implementation references: [NumPy NPZ member-loading semantics](https://numpy.org/doc/stable/reference/generated/numpy.lib.npyio.NpzFile.html),
[PyTorch checkpoint serialization](https://docs.pytorch.org/docs/stable/notes/serialization.html),
[BPE/Unigram trainers](https://huggingface.co/docs/tokenizers/api/trainers),
and [Ultralytics detection formats](https://docs.ultralytics.com/datasets/detect/).
These guide feasibility checks; they are not evidence that Datelier has passed
the corresponding dependency or behavior gates.

## Phase 9 — Editor tabs and whole-session workspaces

- [x] **Phase complete.** **Entry:** M7.2 and the source package refactor pass; existing workspace compatibility tests are available. **Exit:** M9.1–M9.4 pass, including independent training/test workflows and fresh-process session restoration.

### M9.1 — Independent file sessions and editor tabs

[Verified implementation and resources](docs/phase-9.md) cover file ownership,
native tabs, independent inactive-file jobs, nonblocking closure and M9.2
Welcome/recent opening/editor controls, whole-session recovery and cross-file
comparisons. The completed Phase 10/11 inspection expansion is recorded below;
Phase 13 is the next outstanding phase.

- [x] **Deliverables:** application/file session separation; top file tab bar with switching, reordering, closing, and New Tab; independent source/revision, operations, selections, jobs, analysis settings, and views; dockable panels bound to the active file.
- [x] **Entry gate:** inspect current GuiSession and job/persistence boundaries; define typed file-session ownership and the shared worker lifecycle before introducing tabs.
- [x] **Exit gate:** switching between two files retains independent history, selections, controls, and running jobs; closing a loading/analyzing tab cannot publish into another; docking and the existing one-file workflow remain usable.
- [x] **Verification evidence:** deterministic two-file identity/history fixtures, rapid-switch/close/stale-result tests, native tab and docking smoke, full suite and tab-lifecycle resource measurements.
- [x] **Suggested step commits:** `refactor: isolate file inspection sessions` → `feat: add editor file tabs` → `fix: retire jobs when file tabs close`.

### M9.2 — Welcome, recent sources, and file opening

- [x] **Deliverables:** Welcome on startup and blank tabs, recent files/workspaces, Open Files/Open Folder with multi-file selection; contextual import settings and menu workspace actions replacing Open dataset and Workspace panels.
- [x] **Entry gate:** M9.1 passes; file opening targets a specific session and failures cannot replace another tab's source.
- [x] **Exit gate:** startup/New Tab show Welcome; multiple chosen files open independent tabs; Open Folder lists supported tabular files, with media collections added in M10.4; reopening a source focuses it; recent missing sources and failed imports offer actionable recovery; import options and workspace actions remain accessible.
- [x] **Verification evidence:** recent-source persistence/failure fixtures, multi-open and duplicate-open tests, native welcome/file-picker/menu workflows and layout reset/recovery checks.
- [x] **Suggested step commits:** `feat: open files from welcome tabs` → `feat: remember recent files and workspaces` → `refactor: move import and workspace actions into editor controls`.

### M9.3 — Whole-session workspace persistence

- [x] **Deliverables:** versioned whole-session recipes containing tab order/active tab, source references, independent operations/analysis settings/views, and comparison settings; migration of existing single-source workspaces; per-source restore/relink diagnostics.
- [x] **Entry gate:** M9.2 passes; each file session can capture and restore a recipe without fitted artifacts or shared mutable state.
- [x] **Exit gate:** save/reopen restores independent file state and layout; old workspaces become one-file sessions; missing/changed sources remain recoverable while other tabs are usable; restoration starts no ML, tokenizer training, or playback.
- [x] **Verification evidence:** legacy migration, round-trip, partial recovery and changed-source fixtures; fresh-process native save/reopen/relink; atomic-write/source-preservation and full-suite checks.
- [x] **Suggested step commits:** `feat: save whole-session workspaces` → `feat: migrate single-file workspace recipes` → `feat: recover individual workspace sources`.

### M9.4 — Cross-file profile comparison

- [x] **Deliverables:** dockable comparison view with explicit field mappings, numeric distribution overlays, categorical counts and adjacent statistics; shared bins/category ordering, source labels/colors, count/density normalization and saved comparison settings.
- [x] **Entry gate:** M9.3 passes; prepared profiles and comparisons can identify every contributing file/view/revision.
- [x] **Exit gate:** unequal-size training/test distributions compare correctly; mismatched names can be mapped; incompatible types show diagnostics; edits invalidate only affected comparison results and linked selections stay in their originating file.
- [x] **Verification evidence:** known-distribution and category fixtures, shared-bin/normalization tests, cross-file selection/stale-result tests, native comparison and fresh-process restore, measured multi-file resources.
- [x] **Suggested step commits:** `feat: prepare cross-file profile comparisons` → `feat: compare profiles across editor files`.

## Phase 10 — Interpretations, conditional previews, and record inspection

- [x] **Phase complete.** **Entry:** Phase 9 passes. **Exit:** M10.1–M10.4 pass with nonblocking reference discovery, aligned record inspection, and restored preview settings.

[Verified implementation and acceptance](docs/phase-10.md) cover typed roles,
worker discovery/decoding, CPU/GPU lifecycle, conditional styles, direct media/
line manifests, gallery/detail navigation, fresh-process recovery and measured
table/reference/Inspect resources. Phase 11's completed structured/array/checkpoint
expansion is recorded below; text/image/audio tools remain in Phases 12–14.

### M10.1 — Richer column interpretations

- [x] **Deliverables:** local path, image, audio, and external-text interpretations with explanatory inference and reversible overrides; exact first-source-column ID heuristic after recognizable media/text interpretations; retained named-ID detection elsewhere.
- [x] **Entry gate:** inspect existing roles, replay, profiles, and feature eligibility; preserve the distinction between physical dtype, interpretation, and referenced payload.
- [x] **Exit gate:** at import, a nonempty, fully unique non-null integer/string first source column becomes Identifier unless recognizable media/text wins; empty/duplicate/null-containing columns do not satisfy that rule; floats are not IDs merely through uniqueness; overrides replay without changing values/row identity.
- [x] **Verification evidence:** ordinary IDs, unique prose, image/audio/text paths, empty/null/duplicate and misleading-name fixtures; worker-only inference, undo/redo, feature eligibility and legacy workspace checks. Existing conservative-ID evidence remains historical.
- [x] **Suggested step commits:** `feat: infer media and path interpretations` → `feat: interpret unique first-column identifiers`.

### M10.2 — Nearby reference discovery and lazy previews

- [x] **Deliverables:** exact absolute/dataset-relative resolution followed by indexed filename/stem matching; background indexing of the dataset directory and parent's subtree; editable roots/extension filters, progress, retry and explicit ambiguous-match mappings; lazy image thumbnails and text excerpts.
- [x] **Entry gate:** M10.1 passes; Pillow/Python 3.14 decoding and GUI texture creation/lifetime pass a small Linux probe; shared prioritized jobs and cache invalidation are established.
- [x] **Exit gate:** metadata preview appears without waiting for indexing/decoding; nearby stems resolve when unambiguous, duplicates remain explicit choices, missing/unreadable assets have diagnostics; unchanged cells and revision/source-aware cache results survive switching/relinking.
- [x] **Verification evidence:** duplicate stems across roots/extensions, relative/absolute paths, symlink/root changes, corrupt/missing/changed assets; native scroll/thumbnail smoke, decode/index cancellation or abandonment, CPU/GPU retention and latency measurements.
- [x] **Suggested step commits:** `feat: index nearby media references` → `feat: resolve ambiguous file references` → `feat: prepare lazy cell previews`.

### M10.3 — Conditional table presentation

- [x] **Deliverables:** prepared typed cell presentation metadata, numeric blue-to-red shading with percentile/linear/custom scales and marked extremes, stable categorical colors, emphasized nulls, interpretation badges and saved per-view controls.
- [x] **Entry gate:** M10.2 passes; presentation uses prepared values/roles rather than parsing rendered strings or computing table-wide statistics in frames.
- [x] **Exit gate:** nulls differ from literal NULL strings; constant/nonfinite and high-cardinality columns have readable outcomes; selection remains distinguishable; theme changes, sort/filter/undo and workspace restoration retain correct styles and bounded rendering.
- [x] **Verification evidence:** typed-null/category/numeric-extreme fixtures, palette/scale behavior, native light/dark and linked-selection checks, virtualization/resource gates and preference/workspace round trips.
- [x] **Suggested step commits:** `feat: prepare typed conditional cell styles` → `feat: color table previews by interpretation`.

### M10.4 — Shared Inspect view and direct media sources

- [x] **Deliverables:** gallery and focused-record views for row ranges, linked selections and seeded random samples, with any chosen supporting columns; virtual record collections from individual media files/folders and configurable text file-versus-line records.
- [x] **Entry gate:** M10.3 passes; stable file/view/record identities and lazy reference previews are available.
- [x] **Exit gate:** Inspect follows the correct records after sort/filter/sample and cross-file switching; supporting-column choices are not limited by the preview page width; folder manifests and missing records restore predictably. Full modality tools arrive in Phases 12–14.
- [x] **Verification evidence:** seeded range/sample identity and supporting-column fixtures, folder/line provenance and changed-source recovery, native gallery/detail navigation and tab-closure cleanup.
- [x] **Suggested step commits:** `feat: open media files and folders as records` → `feat: inspect selected records with supporting columns`.

## Phase 11 — Structured objects, arrays, and checkpoints

[Verified structured browsing, lazy array inspection, record mappings and CPU checkpoints](docs/phase-11.md)
pass M11.1–M11.4, including native restoration, full-suite/resource checks and
clean installations with and without the optional checkpoint dependency.

- [x] **Phase complete.** **Entry:** Phase 10 passes. **Exit:** M11.1–M11.4 pass; structure, mappings and source-record identity survive workspace restoration without eager payload loading.

### M11.1 — Structured JSON and TOML browsing

- [x] **Deliverables:** expandable object trees, scalar previews and navigation for arbitrary JSON/TOML; retained flat JSON table imports; selected record nodes opened as named table views while the original object remains browsable.
- [x] **Entry gate:** file sessions support typed source kinds and named record views; existing JSON correctness and nested-input diagnostics are covered.
- [x] **Exit gate:** nested objects/arrays are preserved rather than silently flattened; selected compatible records enter the table pipeline with stable node/record provenance; incompatible/mixed structures produce actionable diagnostics and do not alter other views.
- [x] **Verification evidence:** nested/scalar/empty/malformed JSON/TOML fixtures, table extraction and source preservation, native tree/navigation/table workflows, old JSON regressions and workspace node-view restoration.
- [x] **Suggested step commits:** `feat: browse structured json and toml` → `feat: inspect object records as table views`.

### M11.2 — Lazy NPY and NPZ array browsing

- [x] **Deliverables:** member names, shapes, dtypes and storage sizes before payload loading; vector plots, matrix heatmaps and higher-dimensional slice controls; selected compressed NPZ members decompressed in workers to reusable temporary NPY storage and memory-mapped slices where needed.
- [x] **Entry gate:** M11.1 passes; verify NumPy header/member access, mapping, temporary-storage lifecycle and renderer boundaries on representative arrays.
- [x] **Exit gate:** opening an archive does not materialize every member; selecting/slicing preserves dtype and raw values; compressed members remain inspectable through explicit background preparation; corruption, unsupported payloads and disk failures have recoverable diagnostics.
- [x] **Verification evidence:** compressed/uncompressed, empty/structured/string/nonfinite and higher-dimensional fixtures; unselected-member loading checks; native slice/heatmap workflow, cache/disk cleanup and memory/latency measurements.
- [x] **Suggested step commits:** `feat: browse numpy array metadata` → `feat: cache selected npz members for slicing` → `feat: inspect array slices and heatmaps`.

### M11.3 — Confirmable array record mappings

- [x] **Deliverables:** suggested record axes, image/channel and audio layouts, aligned supporting arrays, and confirmation/edit controls; named record views with persisted mappings and stable source-index identity.
- [x] **Entry gate:** M11.2 passes; arrays and scalar supporting columns share references without copying media into the Polars table.
- [x] **Exit gate:** images[N,H,W,C] plus labels[N] form correctly aligned records only after confirmation; alternate layouts/record axes are configurable; unequal lengths are diagnosed without truncation; filtering/sampling/undo and workspace reopen retain alignment.
- [x] **Verification evidence:** NHWC/NCHW and grayscale/heatmap/waveform fixtures, axis ambiguity and length mismatches, mapping round trips, native confirmation and supporting-column/linked-selection checks.
- [x] **Suggested step commits:** `feat: configure array record mappings` → `feat: link array payloads with supporting records`.

### M11.4 — PyTorch checkpoint inspection

- [x] **Deliverables:** CPU inspection of compatible .pt/.pth/.ckpt tensor containers and state dictionaries, nested metadata, shapes/dtypes and tensor plots/slices; explicit PyTorch installation extra and restricted loading with weights_only=True and map_location="cpu"; saved tensor/view locators.
- [x] **Entry gate:** M11.3 passes; verify CPU PyTorch clean install and checkpoint/tensor loading on Python 3.14/Linux, including metadata-first or mapped access where supported.
- [x] **Exit gate:** supported checkpoint contents are inspectable without model construction/inference or unrestricted unpickling; unsupported objects have clear diagnostics; selected tensor values and views restore correctly and cannot overwrite sources or publish stale results.
- [x] **Verification evidence:** nested state-dict/tensor/metadata and unsupported-checkpoint fixtures, CPU placement/value correctness, native tensor navigation, absent-extra diagnostics, checkpoint resource and clean-install checks.
- [x] **Suggested step commits:** `build: add optional cpu checkpoint inspection` → `feat: browse pytorch checkpoints and tensors`.

## Phase 12 — Text profiling and token inspection

[M12.1–M12.4 evidence](docs/phase-12.md) verifies tokenization, local training,
exact corpus profiles, full token-span Inspect, shared-tokenizer cross-file
comparisons, native/restoration/resource gates and clean installations.
The authorized [text navigation follow-up](docs/text-profiles-navigation.md) places
these tools in Explore → Profiles, selected through the shared column checklist.
The [Inspect navigation follow-up](docs/inspect-navigation.md) places record
inspection in Explore → Inspect alongside Profiles, Relationships and Correlations.

- [x] **Phase complete.** **Entry:** Phase 11 passes. **Exit:** M12.1–M12.4 pass; multilingual text statistics and token spans are correct and cross-file comparisons use compatible tokenization.

### M12.1 — Configurable tokenization

- [x] **Deliverables:** character (Unicode code points), whitespace, word, BPE and Unigram modes; visible normalization and token-count settings; local tokenizer configuration loading and source-preserving token offsets.
- [x] **Entry gate:** verify Hugging Face Tokenizers on Python 3.14/Linux; inline/external text records have encoding diagnostics and stable identity.
- [x] **Exit gate:** modes tokenize known multilingual fixtures with documented units and normalization; null/empty/decoding errors have distinct outcomes; imported tokenizer identity and settings are reproducible and no downloads/training occur implicitly.
- [x] **Verification evidence:** Unicode, punctuation, whitespace, empty/null and imported-tokenizer fixtures; offset/normalization tests, native tokenizer controls and saved-setting recovery.
- [x] **Suggested step commits:** `build: establish local tokenization support` → `feat: configure text tokenization modes`.

### M12.2 — Explicit local BPE and Unigram training

- [x] **Deliverables:** explicit training on selected text records, visible training settings, local tokenizer artifacts and training-source provenance; cancellable or safely abandoned jobs; imported/trained configuration persistence.
- [x] **Entry gate:** M12.1 passes; training records and normalization are selectable without hidden corpus inclusion.
- [x] **Exit gate:** training begins only on command, produces reusable BPE/Unigram tokenizers and records its inputs/settings; failures/abandonment leave prior settings intact; reopening references the saved artifact without retraining or downloading.
- [x] **Verification evidence:** small deterministic training corpora, selected-row provenance and artifact round trips, missing/changed tokenizer recovery, worker lifecycle and native explicit-training checks.
- [x] **Suggested step commits:** `feat: train local text tokenizers` → `feat: retain tokenizer provenance and references`.

### M12.3 — Text statistics and profiles

- [x] **Deliverables:** document/token totals; length mean/std/min/max/median/quantiles; vocabulary size, token/document frequencies, hapax counts/ratios, type-token ratio and Shannon entropy in bits; length distributions and token-frequency views with visible corpus scope.
- [x] **Entry gate:** M12.2 passes; statistical preparation runs in workers and keys results by text/tokenizer/settings/revision.
- [x] **Exit gate:** hand-calculated corpus statistics match; nulls, empty documents, decoding failures and special-token handling are reported explicitly; complete collection calculations require a command and exact statistics remain accessible when preview displays are bounded.
- [x] **Verification evidence:** known count/hapax/entropy/length fixtures, empty-corpus outcomes, settings/revision invalidation, native profile/statistics displays and corpus resource measurements.
- [x] **Suggested step commits:** `feat: calculate corpus token statistics` → `feat: profile text lengths and token frequencies`.

### M12.4 — Token inspection and cross-file text comparison

- [x] **Deliverables:** full text, token pieces/IDs, offsets and highlighted spans beside supporting columns in Inspect; cross-file length/statistic/token-frequency comparisons using a shared tokenizer configuration.
- [x] **Entry gate:** M12.3 passes; prepared text/tokens and comparison results retain the correct source-record identity.
- [x] **Exit gate:** token spans map to original multilingual text, long text remains navigable, incompatible tokenizers cannot silently produce equivalent-looking comparisons, and record choices/comparison settings restore without training.
- [x] **Verification evidence:** original-span and long-text fixtures, shared/incompatible tokenizer comparisons, native token highlighting and linked selection, fresh-process workspace and resource checks.
- [x] **Suggested step commits:** `feat: inspect token spans and text records` → `feat: compare text profiles across files`.

## Phase 13 — Images, heatmaps, and detection annotations

- [ ] **Phase complete.** **Entry:** Phase 12 passes. **Exit:** M13.1–M13.4 pass; images, numeric heatmaps and box overlays retain correct values, provenance and geometry.

### M13.1 — Image inspection and collection profiles

- [ ] **Deliverables:** full-resolution zoom/pan, channel controls and pixel readouts, dimensions/aspect ratios, color/channel distributions and explicit collection summaries; support files/folders, metadata-table references and mapped image arrays.
- [ ] **Entry gate:** lazy previews, Inspect navigation and array mappings pass; verify original-resolution decoding and texture lifecycle independently of frame rendering.
- [ ] **Exit gate:** original image dimensions/pixels and collection statistics match known fixtures; supporting columns remain aligned; corrupt/missing assets are counted visibly; complete statistics remain available without requiring every image to stay decoded.
- [ ] **Verification evidence:** grayscale/RGB/RGBA, orientation, varied-size and array-backed images; known color distributions, native zoom/pan/pixel inspection, exact/sampled provenance and decode/cache resource gates.
- [ ] **Suggested step commits:** `feat: inspect full-resolution images` → `feat: profile image dimensions and colors`.

### M13.2 — Numeric heatmap inspection

- [ ] **Deliverables:** numeric image-like array inspection with selectable colormaps/ranges, channels/slices, nonfinite indicators and raw-value readouts; display normalization independent of source values/statistics.
- [ ] **Entry gate:** M13.1 passes; Phase 11's array slicing and image navigation share prepared data without treating arbitrary numeric arrays as encoded RGB automatically.
- [ ] **Exit gate:** signed/float/constant/nonfinite arrays show correct ranges and raw values; changing display normalization does not mutate data or statistical results; mapped record identity remains correct.
- [ ] **Verification evidence:** known-value heatmaps, negative/constant/nonfinite fixtures, slice/readout correctness, native colormap/range navigation and restored settings.
- [ ] **Suggested step commits:** `feat: inspect numeric image heatmaps` → `feat: configure heatmap display ranges`.

### M13.3 — Detection annotation adapters and image association

- [ ] **Deliverables:** Pascal VOC XML, YOLO detection text, COCO JSON and Ultralytics dataset manifests/labels; shared pixel-coordinate boxes retaining original coordinates, classes, optional scores and provenance; explicit image-key/path mappings.
- [ ] **Entry gate:** M13.2 passes; verify format coordinate conventions and minimal manifest-parser dependencies against representative fixtures without adding model inference.
- [ ] **Exit gate:** each named format resolves known boxes to the correct image; normalized/pixel and indexing conversions are explicit; class mappings, missing labels, invalid boxes and ambiguous image associations have diagnostics rather than silent reassignment.
- [ ] **Verification evidence:** equivalent cross-format boxes, normalized edge cases, duplicate stems/class mappings, missing/invalid/out-of-bounds annotations and source-preservation tests.
- [ ] **Suggested step commits:** `feat: load voc and yolo box annotations` → `feat: load coco and ultralytics detection datasets` → `feat: associate annotations with image records`.

### M13.4 — Box overlays, annotation profiles, and image comparisons

- [ ] **Deliverables:** selectable box/class/score overlays with multiple annotation sources; class counts, box size/aspect-ratio and annotation-quality profiles; cross-file image dimension/color comparisons with saved inspection settings.
- [ ] **Entry gate:** M13.3 passes; image-space geometry and source-record identities are available to rendering without annotation parsing in frames.
- [ ] **Exit gate:** overlays stay aligned under zoom/pan and orientation transforms; multiple sources can be inspected on one image; profiles and linked selections match known annotations; workspaces restore mappings without editing annotation files.
- [ ] **Verification evidence:** native cross-format geometry and source-toggle smoke, overlay picking and row alignment, known annotation statistics, fresh-process image/box comparison restore and resource checks.
- [ ] **Suggested step commits:** `feat: overlay and compare detection annotations` → `feat: profile boxes and compare image collections`.

## Phase 14 — Audio inspection and integrated acceptance

- [ ] **Phase complete.** **Entry:** Phase 13 passes. **Exit:** M14.1–M14.4 pass, including actual Linux playback, correct signal views, mixed-source session recovery, and clean installation.

### M14.1 — Lazy audio loading and signal profiles

- [ ] **Deliverables:** common local audio inputs including WAV/FLAC/OGG/MP3 and mapped waveform arrays; header-first sample rate/channel/duration metadata; amplitude/RMS, clipping and silence statistics; sample-rate configuration when arrays lack it.
- [ ] **Entry gate:** verify SoundFile/SoundDevice/SciPy and decoder/system requirements on Python 3.14/Linux; establish worker-side block decoding and preserved original signal metadata.
- [ ] **Exit gate:** files and arrays expose correct duration/channels/rate and known signal statistics; missing-rate arrays require configuration; malformed/unsupported inputs have diagnostics; headers and visible previews do not trigger full collection decoding.
- [ ] **Verification evidence:** mono/stereo, varied-rate, silence/clipping, corrupt/missing and array-backed fixtures; codec feasibility, known signal values, worker lifecycle and memory/latency measurements.
- [ ] **Suggested step commits:** `build: establish linux audio inspection dependencies` → `feat: load audio metadata and waveform records` → `feat: profile audio signal statistics`.

### M14.2 — Waveform, spectrogram, and mel views

- [ ] **Deliverables:** worker-prepared waveform envelopes, spectrograms and mel spectrograms; channel/time-range, FFT/window/hop, mel-band/frequency-limit and scale controls; bounded display preparation with full-resolution access.
- [ ] **Entry gate:** M14.1 passes; signal conversion/preparation has explicit provenance and never silently changes original sample rates.
- [ ] **Exit gate:** known tones/impulses produce correct time/frequency/mel representations; channel/window/range changes invalidate affected work only; long recordings remain navigable and settings/provenance restore accurately.
- [ ] **Verification evidence:** reference signal/frequency and mel-filter fixtures, envelope extrema and time-axis alignment, native waveform/mel controls, long-recording resource and stale-result gates.
- [ ] **Suggested step commits:** `feat: prepare waveform and spectral views` → `feat: inspect configurable mel spectrograms`.

### M14.3 — Listening and cross-file audio comparison

- [ ] **Deliverables:** play/pause/stop, seeking, volume and selected-range playback in Inspect with supporting columns; cross-file audio-statistic profiles and saved view controls; no autoplay.
- [ ] **Entry gate:** M14.2 passes; a bounded playback-buffer/device lifecycle is established independently of GUI rendering.
- [ ] **Exit gate:** actual Linux playback follows the selected record/range and reports device failures; seeking/stop/tab closure release playback resources; loading/restoring never starts sound; audio comparisons retain source identity and compatible units.
- [ ] **Verification evidence:** playback lifecycle/device-error and range-buffer tests, actual listening/seek/pause/volume observations on reference Linux hardware, native supporting-column/comparison workflows and workspace restore.
- [ ] **Suggested step commits:** `feat: listen to selected audio records` → `feat: compare audio profiles across files`.

### M14.4 — Integrated multimodal and local-install acceptance

- [ ] **Deliverables:** representative mixed text/image/audio and NPZ-backed workflows, training/test comparisons, session recovery/relinking, closure/cache-eviction hardening and updated local installation/usage documentation.
- [ ] **Entry gate:** M14.3 and every preceding Phase 9–14 milestone pass; all required dependency and fixture-specific resource budgets are recorded.
- [ ] **Exit gate:** full suite, Pyrefly/Ruff, fresh-process mixed-session and legacy workspace workflows, native modality controls, source preservation and resource/cleanup gates pass; clean Linux install verifies both the base application and checkpoint extra with documented codec/playback requirements.
- [ ] **Verification evidence:** commands/commits/versions, fixtures and manual GUI/listening observations, single-table regression and multimodal CPU/GPU/memory/disk reports, repeated-tab lifecycle runs, clean-wheel workflows and documented material limitations. Existing unfinished Titanic usability gates remain separate.
- [ ] **Suggested step commits:** `fix: harden mixed-source inspection lifecycles` → `docs: document editor and multimodal workflows` → `test: verify multimodal session and local-install acceptance`.

### Roadmap planning verification

Documentation checks pass: Python local-link/anchor and fenced-code audits cover
all 19 Markdown documents and 212 local references; milestone-field/status
checks cover six new phases and 24 milestones; `git diff --check` passes.
All 132 existing checkboxes retain their status and text apart from corrected
M6.1/M6.2 evidence-link targets. Only `ROADMAP.md` and `AGENTS.md` changed.
Application tests, Pyrefly, dependency probes, and GUI/resource gates were not
run for that documentation-only step; all Phase 9–14 implementation gates
were unchecked then. The first implementation gate at approval was M9.1;
[Phase 9 evidence](docs/phase-9.md) records subsequent implementation progress.
