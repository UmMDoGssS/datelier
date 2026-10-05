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
execution, images, and text are post-v1 investigations.

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
  v1 install gate and a concrete personal-use need.
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
- [x] **Verification evidence:** [M6.1 evidence](docs/phase-6.md#m61-referenced-source-workspace-persistence): 312 full-suite tests, Pyrefly/Ruff, strict recipe/source/replay/job tests and live save/restart/relink/redo/selection checks pass; no implicit ML.
- [x] **Step commits:** `3e5464c` versioned recipes → `7d9d494` background restore/relink → `2b513b4` GUI controls, CLI and M6.1 acceptance evidence.

### M6.2 — Saved layouts, themes, and plot preferences

- [x] **Deliverables:** dock layout persistence, configurable themes, saved plot preferences, usable restoration controls.
- [x] **Entry gate:** M6.1 passes and docking/plot controls are already functional.
- [x] **Exit gate:** layout/theme/preferences persist across restart; workspace restoration preserves valid views; unusable layouts can be reset without losing dataset recipes.
- [x] **Verification evidence:** [M6.2 evidence](docs/phase-6.md#m62-saved-layouts-themes-and-plot-preferences): 333 full-suite tests, Pyrefly/Ruff, independent preference recovery, three fresh-process rearrange/restart/default/reset/restore GUI checks and linked-selection/gesture regressions pass.
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

### M8.1 — Windows/macOS distribution

- [ ] **Deliverables:** platform compatibility and packaging proposals for Windows and macOS, assessed separately.
- [ ] **Entry gate:** M7.2 passes; target-platform test environments are available.
- [ ] **Exit gate:** each proposed platform has verified GUI/dependency feasibility and an approved support, packaging, and acceptance specification.
- [ ] **Verification evidence:** installation/launch smoke results, platform-specific issues, supported interpreter/architecture findings, and proposal decisions.
- [ ] **Suggested step commits:** `docs: assess windows distribution` → `docs: assess macos distribution` → `docs: specify platform rollout`.

### M8.2 — Additional data formats

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

- [ ] **Deliverables:** image-dataset inspection proposal grounded in representative analyst workflows.
- [ ] **Entry gate:** M7.2 passes and concrete image use cases and representative data are available.
- [ ] **Exit gate:** an approved specification defines input/data identity, previews, inspection interactions, analysis scope, resource constraints, and delivery gates.
- [ ] **Verification evidence:** dataset/workflow findings, preview and storage feasibility, reuse of workbench components, and proposal decisions.
- [ ] **Suggested step commits:** `docs: investigate image inspection` → `docs: specify image workbench milestones`.

### M8.6 — Text inspection

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
- [ ] Organize GUI; existing workflow, workspace and scatter Mesa smoke checks
  pass alongside focused tests, Pyrefly and Ruff.
- [ ] Final acceptance: full suite, wheel build, isolated installed CLI/workflow,
  stale-import/source-link audit and diff review pass with recorded evidence.

### Verification evidence

Planning baseline: all 94 non-bootstrap root modules have a subsystem assignment;
the existing `feasibility` package stays intact. The existing suite collects
493 tests. Behavioral and installed-package acceptance remain open.

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
