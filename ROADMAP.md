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
[Phase 4 evidence](docs/phase-4.md) records its passed gates. Phase 5 and later
milestones remain unchecked.

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
  Phase 8 investigations are independent; each requires the v1 release gate.
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

- [ ] **Deliverables:** multi-column histogram/KDE/ECDF/box/violin comparisons, independent scatter axes and column colors, Pearson heatmap and bounded pair grid.
- [ ] **Exit gate:** comparison/statistics/identity tests, live mode/navigation/selection checks, and existing inspection resource budgets pass.
- [ ] **Verification evidence:** [incremental evidence](docs/richer-inspection.md); final extension gates remain open.

## Phase 5 — On-demand unsupervised analysis

- [ ] **Phase complete.** **Entry:** Phase 4 passes. **Exit:** M5.1, M5.2 and M5.3 pass.

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

- [ ] **Deliverables:** raw XYZ and three-component embedding plots, column/cluster colors, linked projected picking/brushing and camera gestures.
- [ ] **Exit gate:** 3D source identity, renderer/gesture checks and final inspection/analysis resource gates pass; evidence recorded.
- [ ] **Verification evidence:** 3D correctness/GUI checks, full regression suite, large/wide live frame/memory measurements and final workflow checks.

## Phase 6 — Workspaces and customization

- [ ] **Phase complete.** **Entry:** Phase 5 passes. **Exit:** M6.1 and M6.2 pass.

### M6.1 — Referenced-source workspace persistence

- [ ] **Deliverables:** versioned workspace files with source references, import options, operation recipes, analysis settings, and views; source detection/relinking.
- [ ] **Entry gate:** operations, plot configuration, and analysis settings have typed representations and reproducible behavior.
- [ ] **Exit gate:** save/reopen restores the intended workspace; missing/changed sources are detected; relinking works; loading settings does not automatically rerun ML.
- [ ] **Verification evidence:** save/load/replay round trips, malformed/unsupported workspace handling, moved/changed source fixtures, failed-load state preservation, and reopen GUI checks.
- [ ] **Suggested step commits:** `feat: save workspace recipes` → `feat: restore referenced workspaces` → `feat: detect and relink workspace sources`.

### M6.2 — Saved layouts, themes, and plot preferences

- [ ] **Deliverables:** dock layout persistence, configurable themes, saved plot preferences, usable restoration controls.
- [ ] **Entry gate:** M6.1 passes and docking/plot controls are already functional.
- [ ] **Exit gate:** layout/theme/preferences persist across restart; workspace restoration preserves valid views; unusable layouts can be reset without losing dataset recipes.
- [ ] **Verification evidence:** settings round trips, missing/outdated preference handling, GUI rearrange/restart/reset checks, and linked-selection behavior after restore.
- [ ] **Suggested step commits:** `feat: persist dock layouts` → `feat: customize and save themes` → `feat: restore plot preferences`.

## Phase 7 — V1 hardening and release

- [ ] **Phase complete.** **Entry:** Phases 0–6 pass. **Exit:** M7.1 and M7.2 pass.

### M7.1 — End-to-end correctness and performance

- [ ] **Deliverables:** complete workflow coverage, pathological-input regression cases, measured performance against documented budgets.
- [ ] **Entry gate:** every v1 capability has passed its milestone; benchmark environment, fixtures, budgets, and algorithm limits are recorded.
- [ ] **Exit gate:** import → inspect → transform → plot → analyze → save/reopen → export workflows pass; pathological data and job failures are handled; measured budgets pass.
- [ ] **Verification evidence:** full automated checks, representative end-to-end GUI runs, per-format workflows, source/identity invariants, wall-time/peak-memory reports, and resolved regression results.
- [ ] **Suggested step commits:** `test: cover complete analysis workflows` → focused `fix:` commits for discovered failures → measured `perf:` commits where needed → `docs: record acceptance evidence`.

### M7.2 — Linux release readiness

- [ ] **Deliverables:** installable build artifacts, working CLI launch, setup/usage documentation, complete v1 release checklist.
- [ ] **Entry gate:** M7.1 passes and no required v1 gate remains open.
- [ ] **Exit gate:** a clean Linux environment can install and launch the built package and complete a representative workflow using the documentation; release version/metadata and checklist are consistent.
- [ ] **Verification evidence:** build/install commands, clean-environment launch and workflow observations, README walkthrough, full check outcomes, and checklist with no unresolved required items.
- [ ] **Suggested step commits:** `build: prepare linux distribution` → `docs: document installation and workbench usage` → `chore: finalize v1 release readiness`.

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
