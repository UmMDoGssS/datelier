# Datelier contributor guide

## Purpose and direction

Datelier is a simple personal desktop data inspection workbench. Keep changes
practical; public release infrastructure and decorative polish are not goals.
Build on the completed tabular baseline. The authorized post-v1 direction adds
editor sessions, structured files, and text/image/audio inspection through
Phases 9–14 of [ROADMAP.md](ROADMAP.md#authorized-editor-and-multimodal-expansion).
Prioritize useful inspection, responsive interactions, and customization over
decorative UI.

The v1 target is Linux, Python 3.14+, and datasets that fit in memory. Use Polars
for tabular operations and Dear ImGui/ImPlot through
[ImGui Bundle](https://github.com/pthom/imgui_bundle/blob/main/docs/book/core_libs/hello_imgui_immapp.md)
for the GUI. Keep the architecture portable, but do not claim support for an
unverified platform. Approximately one million rows is a benchmark direction,
not a capacity guarantee: width, types, and operations affect memory use.

V1 includes:

- CSV/TSV, JSON/JSONL, Parquet, and tabular XML import.
- Immediate table previews, schema and quality summaries, distributions,
  counts, correlations, and suggested scatter plots.
- Sorting, filtering, column selection, casts, missing-value operations,
  lookup mappings, and derived columns through constrained expressions.
- A reversible operation pipeline, undo/redo, and explicit CSV/Parquet export.
- On-demand PCA, t-SNE, UMAP, and k-means with visible settings and provenance.
- Saved workspaces, dockable panels, themes, plot controls, and linked
  table/plot selections.

Third-party plugins, arbitrary Python mappings, larger-than-memory table
execution, additional platforms, and image/text/audio inspection are outside
the completed v1 scope. Phases 9–14 authorize the concrete editor and multimodal
expansion; other directions remain optional investigations. Lazy media loading
and temporary array caches do not authorize a general out-of-core table engine.
Do not build speculative infrastructure for unrequested directions.

## Repository state and sources of truth

The repository has a Python 3.14+ `uv`-managed `src/` package, configured Pyrefly,
pytest, and Ruff, and a locked Polars/ImGui Bundle/analysis dependency set.
Phase 0 has passed its clean-install, docking/plot, tiny-analysis, and synthetic
benchmark gates; evidence and acceptance budgets are in
[docs/phase-0.md](docs/phase-0.md). Phase 1 has passed CSV import/state and
responsive preview/job gates;
[docs/phase-1.md](docs/phase-1.md) records evidence. Phase 2 has passed format
coverage and tabular XML/nested-input gates;
[docs/phase-2.md](docs/phase-2.md) records correctness, GUI, and memory evidence.
The CLI opens the tabular workbench by default and retains the synthetic
feasibility window. Linux GUI rendering is verified with Mesa software OpenGL
on the reference machine; accelerated rendering remains unverified.
Phase 3 has passed reversible-operation/history, typed-transform/expression,
and explicit CSV/Parquet export gates; [docs/phase-3.md](docs/phase-3.md) records
correctness, GUI, and resource evidence. Phase 4 has passed automatic
profiles/plots and configurable linked-selection gates;
[docs/phase-4.md](docs/phase-4.md) records correctness, GUI, and resource
evidence. The richer Phase 4 extension has passed multi-column comparisons,
independent axes/colors and relationship heatmap/grid gates;
[docs/richer-inspection.md](docs/richer-inspection.md) records evidence.
Phase 5 has passed explicit PCA/k-means/t-SNE/UMAP, worker lifecycle, provenance,
3D linked interaction and final resource gates;
[docs/phase-5.md](docs/phase-5.md) records correctness, GUI and resource evidence.
Phase 6 has passed referenced-workspace restore/relink, saved-layout/theme/plot
preference and recovery gates; [docs/phase-6.md](docs/phase-6.md) records
correctness and fresh-process GUI evidence. Phase 7 has passed end-to-end
hardening and local Linux installation; [docs/phase-7.md](docs/phase-7.md) records
workflow, resource and clean-wheel evidence. The personal-use v1 scope is complete.
Further work should follow a concrete need; Phase 8 of [ROADMAP.md](ROADMAP.md)
lists optional investigations, not an automatic feature backlog.

The concrete Titanic inspection UX follow-up is authorized and underway;
[docs/ux-implementation.md](docs/ux-implementation.md) tracks verified slices
against [docs/ux-titanic-review.md](docs/ux-titanic-review.md). Keep unfinished UX
gates open; completed v1 capability gates do not imply usability acceptance.
The user also authorized broader unsupervised inspection methods and explicit
Colors sources; [docs/unsupervised-methods.md](docs/unsupervised-methods.md) tracks
that expansion and its verification gates.
The Schema/profile checklist and statistics follow-up is authorized;
[docs/profile-comparison.md](docs/profile-comparison.md) tracks its delivery gates.
The categorical inspection follow-up is also authorized;
[docs/categorical-inspection.md](docs/categorical-inspection.md) records column
roles and reversible overrides, Relationships charts, and pair-grid diagonal
representations. Keep statistical preparation out of GUI callbacks and retain
the distinction between physical types and user-controlled analysis roles.
The category distribution clarification is authorized;
[docs/category-distribution-follow-up.md](docs/category-distribution-follow-up.md)
tracks box/violin Relationships and single-column count routing to Profiles.
The scatter views and native legend follow-up is authorized;
[docs/scatter-views-and-legends.md](docs/scatter-views-and-legends.md) tracks
separate 2D/3D scatter views, fixed component counts and plot legend verification.

The editor and multimodal expansion is authorized for staged delivery in
[ROADMAP.md](ROADMAP.md#authorized-editor-and-multimodal-expansion): independent
file tabs and whole-session workspaces, cross-file profile comparisons, richer
interpretations and previews, structured JSON/TOML and NPY/NPZ/checkpoint
inspection, text tokenization/statistics, image/box inspection, and audio
profiles/playback. Phase 9 passes independent tabs/shared workers, Welcome/recent
sources/editor controls, whole-session persistence/recovery and cross-file profile
comparisons; [docs/phase-9.md](docs/phase-9.md) records correctness, native input,
fresh-process restoration and measured multi-file resources. Phase 10 passes
richer interpretations, nearby reference discovery/lazy previews, conditional
table styles, gallery/detail Inspect and direct media/text record collections;
[docs/phase-10.md](docs/phase-10.md) records correctness, native restoration and
measured resource gates. Phase 11 passes structured JSON/TOML browsing and named
record views, lazy NumPy member/slice inspection, confirmed array record
mappings with aligned supporting fields and optional restricted CPU checkpoint
inspection;
[docs/phase-11.md](docs/phase-11.md) records source/provenance, native restoration
and measured resource evidence, full-suite checks and clean base/CPU installs.
Phase 12 passes configurable local tokenization, explicit selected-record
BPE/Unigram training/provenance, saved-artifact recovery, exact corpus profiles,
complete original token-span Inspect and shared-tokenizer text comparisons;
[docs/phase-12.md](docs/phase-12.md) records multilingual correctness, native
selection/restoration, measured corpus/long-record resources, full-suite checks
and clean base/CPU-extra installs. Text tools now live in Explore → Profiles;
[docs/text-profiles-navigation.md](docs/text-profiles-navigation.md) tracks selection
and restoration checks for this navigation follow-up.
Inspect now shares Explore's tab row with Profiles, Relationships and Correlations;
[docs/inspect-navigation.md](docs/inspect-navigation.md) records native navigation,
direct media opening and saved-session restoration checks.
Phase 13 passes: M13.1 delivers original-pixel file/array Inspect, explicit
exact/sampled collection profiles, saved controls and measured resource gates;
[docs/phase-13.md](docs/phase-13.md) records evidence. M13.2 also passes numeric
heatmap channels/slices, display-only colormaps/ranges, exact values and native
saved-record restoration. M13.3 passes VOC/YOLO/COCO/local manifest adapters,
explicit source/image-key association controls, saved mappings, native restoration
and header-only resource gates. M13.4 passes multiple-source overlays, annotation
profiles and scoped cross-file image comparisons, saved controls and idle
fresh-process restoration. Dense-label avoidance and cached viewport scenes pass
the native overlay budget; exact/sampled comparisons pass bounded retention and
source-preservation resource checks. Full-suite and final acceptance evidence are
in [docs/phase-13.md](docs/phase-13.md).
Phase 14 M14.1 passes header-first file/mapped-array audio loading, explicit
original-signal statistics, native Inspect controls and saved configuration;
[docs/phase-14.md](docs/phase-14.md) records codec, correctness, fresh-process
restoration and measured resource evidence. M14.2–M14.4 remain open.
Phase 8 investigations do not block this approved sequence. Existing v1 evidence
and unfinished Titanic usability gates retain their status.

Use this file for durable conventions and `ROADMAP.md` for sequencing,
deliverables, and acceptance gates. Inspect actual code and configuration
before relying on either document's description of current implementation.
Keep both documents aligned when an authorized decision changes direction.

## Architecture and data integrity

- Separate import adapters, dataset and operation state, profiling, plotting
  preparation, analysis, persistence, and GUI rendering. Keep boundaries typed
  and testable without starting the GUI. Introduce shared abstractions only
  when concrete features need them.
- Keep Polars as the table engine. Convert selected data to NumPy or pandas
  only at a library boundary where the conversion is justified; avoid routine
  whole-table copies or a second authoritative table representation.
- Preserve source files. Represent transformations as ordered, replayable
  operations against a source dataset, with undo/redo and explicit export.
  Failed operations must not partially alter the active pipeline.
- Maintain stable row identity independently of display position. Sorting,
  filtering, sampling, preprocessing, and analysis must preserve enough
  identity to link results and selections back to the correct source rows.
- Associate derived data and background jobs with dataset revisions. Reject
  stale results and invalidate affected profiles, plots, and analysis when
  the dataset or pipeline changes.
- Namespace records, selections, jobs, and prepared results by file and record
  view as well as revision. Equal source-row numbers in different files do not
  identify the same record. Closing a tab must prevent its jobs publishing into
  another tab.
- Keep physical types, analysis interpretations, and media/array references
  distinct. Inference must explain its evidence; overrides are reversible and
  persisted. Resolving a reference must not rewrite the original cell value.
- Save source references, import options, operation recipes, analysis settings,
  and views in versioned workspace files. Detect changed/missing sources and
  support relinking. V1 workspaces do not bundle data snapshots by default.
- Whole-session workspaces must preserve independent file/view recipes and
  migrate existing single-source workspaces. Reference media and tokenizer
  artifacts; do not bundle decoded caches or fitted ML results. Preserve usable
  tabs when another source needs recovery or relinking.
- Restrict user expressions to the supported expression interface. Do not
  introduce arbitrary Python execution as a shortcut for mapping.

## GUI, computation, and customization

- Render from prepared state. Keep file reads, table-wide computation, and ML
  outside frame callbacks. Use background jobs and virtualized table rendering.
- Open metadata before decoding media/array payloads. Use shared bounded jobs
  and configurable caches, prioritizing visible records and selected profiles.
  Whole-collection text/media analysis and tokenizer training require explicit
  commands. Cache limits govern retained data rather than remove capabilities;
  use chunking, background work, or temporary storage when needed.
- Show loading, progress where available, errors, and completion. Support
  cancellation where feasible, otherwise safe abandonment that cannot publish
  obsolete results. Do not claim a job has stopped if it is still executing.
- Automatically provide basic inspection and a broad but bounded set of
  type-aware plots. Cap pairwise work on wide tables and let users expand or
  configure it. Clearly label sampling, approximation, and truncation.
- Run PCA, t-SNE, UMAP, and k-means only after an explicit user command.
  Loading a dataset or restoring a workspace must not silently run ML.
  Tokenizer training and audio playback must likewise never start implicitly
  during loading or restoration.
- Expose feature selection, preprocessing, parameters, and random seeds.
  Record them with results and preserve row alignment after excluding inputs.
- Support docking, saved layouts, themes, configurable plots, zoom/pan, and
  linked selections. Keep implementation details out of product controls
  unless they help the user make a meaningful decision.

## Python and tooling conventions

- Prefer grouping related source files into cohesive packages by subsystem.
  Put new modules in the package that owns their responsibility, and create
  subpackages when several files form a meaningful group. Keep the package root
  focused on bootstrap code; avoid unrelated utility folders and redundant
  filename prefixes.
- Write idiomatic, typed Python with explicit function return types, useful
  domain types, and narrow interfaces. Use names and small functions to make
  responsibilities clear. Avoid unnecessary frameworks and indirection.
- Avoid blanket type suppressions and pervasive `Any`. Isolate untyped
  dependency boundaries; justify any narrow suppression at its use site.
- When a file approaches or exceeds 300 lines, reconsider its responsibilities
  and opportunities for meaningful separation. This is a review trigger,
  not a hard cap or a reason to split cohesive code mechanically.
- Use `uv` for environment and dependency management. Keep `pyproject.toml`
  and `uv.lock` consistent; do not hand-edit the lockfile.
- Keep Pyrefly LSP diagnostics enabled in an editor that supports them. Always
  run `uv run pyrefly check` for each implementation step before committing;
  editor diagnostics are not a substitute for the batch check.
- Pytest and Ruff were established in M0.1. Use
  `uv run pytest <relevant tests>`, `uv run ruff check .`, and
  `uv run ruff format --check .` for step verification. Run
  `uv run pytest` at milestone completion, plus the milestone's other gates.

## Mandatory development workflow

1. Inspect relevant code, repository state, and roadmap entry/exit gates.
2. Before coding, split the task into meaningful, bounded, verifiable steps.
   Each step should deliver coherent behavior or a necessary foundation,
   rather than merely finish an arbitrary group of files.
3. Implement one step. Do not implement the entire feature and only then
   begin testing, type checking, and fixing it.
4. Run Pyrefly, focused behavioral tests, Ruff lint/format checks, and a GUI
   smoke check when UI behavior changes. Foundation steps must establish
   their required tools before claiming their verification gate has passed.
5. Fix failures within the current step, rerun affected checks, review the
   diff, and commit the completed step before starting the next one.
6. At milestone completion, run the full suite and milestone-specific
   acceptance checks. Record evidence before marking a gate passed.

Tests should exercise behavior, data invariants, and meaningful failure modes;
avoid tests that simply mirror implementation details. Use deterministic small
fixtures for correctness and separate benchmark fixtures for performance.
Do not require application tests or Pyrefly for documentation-only changes;
review Markdown, links, consistency, and diff whitespace instead.

If a required check cannot run, state the limitation and leave its gate open.
Do not silently waive checks, claim unperformed verification, or present an
unverified step as complete. Summarize what changed, checks actually run,
material limitations, and the next outstanding gate.

## Commits and change discipline

- Use Conventional Commit prefixes: `feat:`, `fix:`, `refactor:`, `test:`,
  `docs:`, `chore:`, `perf:`, `build:`, and `ci:`. Optional scopes are welcome;
  write a concise message describing the concrete change.
- Commit every completed, verified implementation step. Keep commits coherent
  and reviewable; preserve step commits unless the user requests squashing.
- Stage only changes belonging to the step. Preserve unrelated user work;
  do not revert it or include it in your commit.
- Keep dependency/configuration changes and documentation consistent with the
  behavior being introduced. Update milestone status only with evidence.
