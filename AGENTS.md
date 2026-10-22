# Datelier contributor guide

## Purpose and direction

Datelier is a personal Linux desktop data inspection workbench for Python 3.14+
and datasets that fit in memory. Use Polars for tables and Dear ImGui/ImPlot
through ImGui Bundle for rendering. Prioritize useful inspection, responsive
interaction, and customization. Public release infrastructure, decorative polish,
and speculative features are not goals. One million rows is a benchmark direction,
not a capacity guarantee.

The tabular baseline and authorized editor/multimodal expansion are delivered:
independent source/view sessions, reversible transforms, explicit analysis,
referenced workspaces, structured/array/checkpoint sources, text, images,
annotations, and audio. Follow concrete new requests. Third-party plugins,
arbitrary Python mappings, out-of-core tables, and extra platforms need separate
requirements; lazy media stores do not authorize a general out-of-core engine.

## Documentation and current contracts

Keep current technical/behavioral documentation in the owning package, module,
class, or function docstring. Explain non-obvious contracts, units, identity,
failure behavior, and boundaries; avoid restating signatures or documenting
small self-explanatory helpers. Do not recreate standalone feature reports or
duplicate prose across modules. README is a minimal setup/entry point; this file
contains contributor instructions.

Start with [datelier](src/datelier/__init__.py) for scope/setup, then the owning
subsystem. [scripts](scripts/__init__.py) documents current verification commands.
The original roadmap, completed reports, and raw evidence are recoverable at Git
snapshot `b1b332c`; their measurements and retired commands remain historical.
Current code/configuration take precedence over descriptions of old snapshots.

Linux Mesa software rendering is verified; accelerated rendering and other
platforms remain unverified. Actual audio listening was deferred by the user on
2026-10-08 and remains open. The unfinished Titanic human usability gates remain
open in the [GUI package docstring](src/datelier/gui/__init__.py); automated feature
acceptance does not close them. Mouse-selector automation on the historical
nested-column display also remains unverified.

## Architecture and data integrity

Use class-based GUI component families with immediate-child rendering and narrow
prepared state/command injection. Separate application coordination from GUI
presentation; pure drawing/formatting helpers may remain functions. Concrete
immutable algorithm objects own tunable fields, GUI schema, limits, constraints,
estimator construction, and fitting. Extend the trusted catalog/generic forms;
legacy parameter names alias those executable classes. Preserve recipe names.
Family exports must not eagerly load GUI/ML/optional runtimes or higher-level
consumers into lower-level contracts.

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
- Expose cohesive public APIs with explicit re-exports in package `__init__.py`
  files. Keep dependency imports and side effects bounded; family catalogs must
  not load ML estimators or GUI libraries. Inside a family, import concrete
  modules when needed to avoid circular dependencies.
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

1. Inspect relevant code, repository state, and the requested acceptance gates.
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
Documentation-only changes do not require application tests or Pyrefly. Review
docstring accuracy, Markdown links, consistency, formatting, and diff whitespace;
confirm executable syntax is unchanged when migrating documentation.

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
- Keep dependency/configuration changes and nearby docstrings consistent with
  the behavior being introduced. Record acceptance outcomes and material
  limitations in the verified step commit; mark gates passed only with evidence.
