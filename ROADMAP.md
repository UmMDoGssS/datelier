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

The starting repository contains a `uv`-managed `src/` package, a placeholder
`datelier` CLI, an empty README, and configured Pyrefly. Application dependencies,
pytest, and Ruff are not yet established. `.python-version` selects 3.14 while
`pyproject.toml` still permits 3.12+; M0.1 will align them. These documents do
not mean application milestones have been completed.

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

- [ ] **Phase complete.** **Entry:** existing scaffold. **Exit:** M0.1 and M0.2 pass.

### M0.1 — Establish the development baseline

- [ ] **Deliverables:** Python 3.14+ metadata, consistent lockfile, pytest/Ruff configuration, documented check commands.
- [ ] **Entry gate:** inspect the scaffold and contributor conventions; confirm the available Python 3.14 environment.
- [ ] **Exit gate:** clean environment sync and existing CLI launch work; Pyrefly, lint, format checks, and a meaningful baseline test pass.
- [ ] **Verification evidence:** environment/setup commands, interpreter version, CLI result, and complete check outputs; confirm the dev group installs required tools.
- [ ] **Suggested step commits:** `chore: align python target` → `build: establish development checks` → `test: verify baseline launch`.

### M0.2 — Validate stack integration and performance fixtures

- [ ] **Deliverables:** Linux feasibility slice, verified dependency set, synthetic benchmark fixtures, recorded baseline and acceptance budgets.
- [ ] **Entry gate:** M0.1 passes; the GUI can be exercised on a Linux graphical environment.
- [ ] **Exit gate:** docking and an ImPlot plot render; selected Polars data reaches the plot; tiny PCA, t-SNE, UMAP, and k-means runs succeed on Python 3.14.
- [ ] **Verification evidence:** locked dependency versions, GUI smoke observations, algorithm result shapes/finite values, conversion checks, and reproducible benchmark measurements.
- [ ] **Suggested step commits:** `build: establish application dependencies` → `feat: validate gui and table integration` → `test: verify analysis compatibility` → `perf: record feasibility baseline`.

## Phase 1 — First usable inspection slice

- [ ] **Phase complete.** **Entry:** Phase 0 passes. **Exit:** M1.1 and M1.2 pass.

### M1.1 — CSV import and dataset state

- [ ] **Deliverables:** CSV adapter, import options/diagnostics, typed dataset state, stable row identity, dataset revisions.
- [ ] **Entry gate:** stack feasibility passes and Polars import behavior is verified.
- [ ] **Exit gate:** normal CSV files load correctly; empty, malformed, and mixed-type inputs have defined outcomes; row identity is independent of display order.
- [ ] **Verification evidence:** fixture-based schema/value checks, option handling, useful error messages, and source-byte preservation tests.
- [ ] **Suggested step commits:** `feat: define dataset state` → `feat: import csv tables` → `test: cover csv failures and identity`.

### M1.2 — Responsive preview and job lifecycle

- [ ] **Deliverables:** virtualized table, schema/null summaries, background loading, visible job status, revision-aware completion handling.
- [ ] **Entry gate:** M1.1 passes and the import contract supplies data, metadata, and errors without GUI dependencies.
- [ ] **Exit gate:** loading does not block rendering; the preview shows correct rows/types; failures surface; changing datasets prevents an older job from replacing active state.
- [ ] **Verification evidence:** job-state and stale-result tests, rapid-switch and failure GUI smoke checks, large-table preview timings against recorded budgets.
- [ ] **Suggested step commits:** `feat: add background dataset loading` → `feat: render virtualized previews` → `feat: show schema and job status`.

## Phase 2 — Format coverage

- [ ] **Phase complete.** **Entry:** Phase 1 passes. **Exit:** M2.1 and M2.2 pass.

### M2.1 — TSV, JSON/JSONL, and Parquet

- [ ] **Deliverables:** adapters/options for remaining straightforward formats, sharing dataset state, preview, and diagnostics.
- [ ] **Entry gate:** the CSV inspection slice and importer contract pass their gates.
- [ ] **Exit gate:** each format loads equivalent tabular fixtures with appropriate types; malformed/unsupported structures produce actionable diagnostics without corrupting active state.
- [ ] **Verification evidence:** per-format and cross-format schema/value tests, null/type cases, failure tests, and import-to-preview smoke checks.
- [ ] **Suggested step commits:** `feat: support tsv imports` → `feat: support json and jsonl imports` → `feat: support parquet imports`.

### M2.2 — Tabular XML and nested-input handling

- [ ] **Deliverables:** XML adapter, configurable record extraction, explicit nested-data handling, parse/type diagnostics.
- [ ] **Entry gate:** M2.1 passes and format options/errors use the shared importer interface.
- [ ] **Exit gate:** repeated XML records become a correct table; extraction settings are visible; nested XML/JSON is explicitly mapped or clearly rejected rather than silently losing data.
- [ ] **Verification evidence:** XML fixtures covering missing fields, attributes, namespaces, nesting, malformed input, and deterministic extraction; matching diagnostics smoke checks.
- [ ] **Suggested step commits:** `feat: extract tabular xml records` → `feat: expose xml import options` → `fix: clarify nested input diagnostics`.

## Phase 3 — Reversible transformations

- [ ] **Phase complete.** **Entry:** Phase 2 passes. **Exit:** M3.1 and M3.2 pass.

### M3.1 — Ordered operations and undo/redo

- [ ] **Deliverables:** replayable pipeline, sorting, filtering, column selection, undo/redo controls, revision changes.
- [ ] **Entry gate:** stable row identity and revision-aware dataset/job state are established.
- [ ] **Exit gate:** operation order is respected; undo/redo restores expected tables; new edits handle redo history consistently; failures leave the active pipeline intact.
- [ ] **Verification evidence:** known-result pipeline/replay tests, selection identity checks through sorting/filtering, revision invalidation tests, and GUI history smoke checks.
- [ ] **Suggested step commits:** `feat: add operation pipeline` → `feat: add sorting filtering and selection` → `feat: add undo and redo`.

### M3.2 — Mapping, derived columns, and export

- [ ] **Deliverables:** casts, missing-value operations, lookup mappings, constrained expressions, derived columns, explicit CSV/Parquet export.
- [ ] **Entry gate:** M3.1 passes with deterministic replay and tested operation failure behavior.
- [ ] **Exit gate:** transformations replay correctly with type/null diagnostics; expressions cannot execute arbitrary Python; exported tables match the active result and source files remain unchanged.
- [ ] **Verification evidence:** expression/transform success and rejection cases, failed-cast behavior, undo/replay tests, export round trips, and source-preservation checks.
- [ ] **Suggested step commits:** `feat: add typed data transforms` → `feat: add constrained derived expressions` → `feat: export transformed tables`.

## Phase 4 — Automatic and interactive exploration

- [ ] **Phase complete.** **Entry:** Phase 3 passes. **Exit:** M4.1 and M4.2 pass.

### M4.1 — Type-aware profiles and automatic plots

- [ ] **Deliverables:** numeric/categorical/temporal profiles, distributions, counts, correlations, bounded suggested scatter plots, revision-aware prepared plot data.
- [ ] **Entry gate:** table operations and revision invalidation are tested; baseline summaries and background jobs work.
- [ ] **Exit gate:** opening a dataset automatically provides the exploration dashboard; plots match known data; unsuitable columns and excessive pairwise work are handled explicitly.
- [ ] **Verification evidence:** known-summary/distribution/correlation tests, null/nonfinite and constant-column cases, high-cardinality/wide-table limits, and automatic-dashboard smoke checks.
- [ ] **Suggested step commits:** `feat: compute type-aware profiles` → `feat: prepare bounded plot suggestions` → `feat: render automatic exploration dashboard`.

### M4.2 — Plot controls and linked selection

- [ ] **Deliverables:** column/plot controls, zoom/pan, linked table/plot selection, sampling labels, configurable bounded expansion.
- [ ] **Entry gate:** M4.1 passes and plot data carries correct row identity and revision metadata.
- [ ] **Exit gate:** interactions select the correct rows after sort/filter/sample operations; sampling/truncation is visible; wide tables and interaction timings meet recorded limits.
- [ ] **Verification evidence:** row-alignment/selection tests, stale-plot tests, GUI zoom/pan/selection smoke checks, and benchmark results against interaction budgets.
- [ ] **Suggested step commits:** `feat: configure interactive plots` → `feat: link plot and table selections` → `perf: bound interactive plotting work`.

## Phase 5 — On-demand unsupervised analysis

- [ ] **Phase complete.** **Entry:** Phase 4 passes. **Exit:** M5.1 and M5.2 pass.

### M5.1 — Shared analysis flow, PCA, and k-means

- [ ] **Deliverables:** explicit feature/preprocessing controls, analysis job/result state, PCA and k-means, parameters/seeds and input provenance.
- [ ] **Entry gate:** background jobs, revision invalidation, and linked selections pass; algorithm dependencies passed M0.2.
- [ ] **Exit gate:** only an explicit command starts analysis; unsuitable inputs have diagnostics; results record preprocessing/settings and align with included source rows.
- [ ] **Verification evidence:** known PCA structure and separable-cluster fixtures, repeatability checks where supported, preprocessing/excluded-row alignment tests, and command-to-result GUI checks.
- [ ] **Suggested step commits:** `feat: configure analysis inputs` → `feat: run pca analysis` → `feat: run k-means clustering` → `feat: inspect analysis provenance`.

### M5.2 — t-SNE, UMAP, and bounded jobs

- [ ] **Deliverables:** t-SNE/UMAP controls and plots, parameter validation, progress where available, cancellation/safe abandonment, explicit resource limits.
- [ ] **Entry gate:** M5.1 passes and the common analysis flow handles preprocessing, identity, provenance, and failure.
- [ ] **Exit gate:** both algorithms run on eligible data by command; invalid parameters are rejected; abandoned/stale jobs cannot publish results; large inputs use visible limits or sampling.
- [ ] **Verification evidence:** finite embedding/shape and parameter tests, recorded seed behavior, job failure/abandonment/stale-result tests, resource measurements, and GUI lifecycle checks.
- [ ] **Suggested step commits:** `feat: add t-sne analysis` → `feat: add umap analysis` → `feat: bound and abandon analysis jobs`.

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
