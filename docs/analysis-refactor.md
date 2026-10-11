# Analysis algorithm ownership refactor

Authorized on 2026-10-11: replace algorithm dispatch chains with typed abstract
algorithm families, concrete builders, and dynamically rendered parameter schemas.
Preserve all 26 methods, explicit execution, bounded worker resources, stable row
identity, provenance, prediction capabilities and saved workspace recipes.

Automated acceptance is complete. The entries below retain the evidence for each
verified delivery step.

## Delivery and acceptance

1. Execution ownership: concrete `Algorithm`, `ClusteringAlgorithm` and
   `DecompositionAlgorithm` families, trusted registry dispatch, method-owned
   estimator construction, diagnostics and input constraints.
2. Parameter ownership: each method owns its typed schema, defaults and limits;
   application requests and restoration use the catalog, and one GUI renderer
   renders all schemas, including conditional and automatic parameters.
3. Audit and acceptance: exercise all algorithms and parameter forms, saved
   recipes, prediction and failure paths; full pytest/Pyrefly/Ruff and native
   analysis input/workflow checks. Record evidence before completion.

## Step 1 — Execution ownership

The runner now delegates directly to a registered concrete algorithm. The old
clustering, linear and manifold dispatch modules are removed. Method-specific
prepared-input constraints move beside estimator construction and diagnostics.
Family implementations share result validation, noise/label handling, bounded
threads and provenance. Estimator imports remain inside explicit worker execution.
The persisted enum remains the stable identifier; family membership comes from
registered class inheritance.

Verification: `uv run --offline pytest tests/test_analysis*.py -q`: **87 passed**;
full Pyrefly: **0 errors**, one existing HDBSCAN stub suppression; full Ruff lint
and format and diff whitespace pass. No GUI behavior changes in this step.
Parameter schema and GUI migration remain open.

## Step 2 — One schema and one settings path

Every method's typed parameter record now lives with its concrete algorithm.
Class-owned row/default limits feed request bounds and GUI controls. The schema
normalizes dataclass metadata into typed descriptors used by both validation and
one form renderer. Conditional visibility and automatic numeric values use the
same domain descriptors. No GUI algorithm-specific form subclasses remain.

Application drafts use one parameter map and one row-limit map. Request creation
and restoration have no method dispatch chain. Old parameter import paths remain
explicit compatibility exports; serialized class names, fields and algorithm
values are unchanged. Existing numeric or automatic t-SNE learning-rate recipes
round-trip. The original four methods now enforce the numeric/type bounds declared
in their schemas, including the shared one-million numeric upper default; this
closes the previous mismatch between GUI bounds and request validation.

Verification: **176 focused tests pass** (including 34 new schema/recipe/failure
checks); full Pyrefly **0 errors**, Ruff lint/format and whitespace checks pass.
[Native schemas](evidence/analysis-refactor/native-schemas-step2.json): all 26 forms,
boolean/numeric input, automatic/manual draft retention and conditional fields;
307 frames, 15.22 ms p95. [Native explicit analysis workflow](evidence/analysis-refactor/native-workflow-step2.json):
selector, Run, preserved completion focus and Open result; 220 frames, 15.91 ms
p95. Both preserve source bytes. Catalog/default validation in a fresh process
imports neither sklearn/UMAP/Numba nor the GUI.

Prediction ownership and full acceptance remain open.

## Step 3 — Prediction ownership and final acceptance

Clustering algorithms own prediction through their family interface. K-means and
Mini-batch K-means inherit bounded nearest-center prediction in the original
fitted preprocessing space. Label-only methods retain fitting-row identity and
leave unseen rows unassigned. Coloring consumes this interface. Direct builders
reject prepared requests with different parameter settings before fitting.
Workspace codec registration and benchmark defaults also consume the catalog.
Concrete module names now follow normal Python naming conventions.

The [catalog audit](evidence/analysis-refactor/catalog.json) records all 26
methods, families, parameters, defaults, conditions and row limits. Production
execution, input validation, request creation, workspace restoration and parameter
forms contain no algorithm-matching dispatch chain. Each concrete method keeps
its own constructor, fitting/transforming choices, diagnostics, validation and any
special preprocessing, with common result/integrity behavior in abstract families.

Final verification:

- `uv run --offline pytest -q`: **1,187 passed**, three existing dependency
  warnings, 33.78 seconds. Existing tests exercise all 26 algorithms, reproducible
  coordinates/labels, fitting-space predictions, row alignment, invalid inputs,
  worker lifecycle and saved recipes. New tests cover schema updates, independent
  drafts, conditional/type failures, legacy rates, mismatched builders and
  polymorphic prediction.
- Full `uv run --offline pyrefly check`: **0 errors**, one existing narrow
  HDBSCAN stub suppression and 37 existing warnings. Full Ruff lint and format
  (**715 files**) and diff whitespace checks pass.
- [Native schemas](evidence/analysis-refactor/native-schemas.json): all 26 forms,
  boolean, real, integer and choice input, automatic/manual draft retention,
  conditional visibility and no implicit ML; 381 frames, **15.67 ms p95**.
- [Explicit analysis](evidence/analysis-refactor/native-workflow.json): native
  features → Run → Open result, preserved completion focus; 221 frames,
  **17.07 ms p95**.
- [Scatter](evidence/analysis-refactor/native-scatter.json): native 2D/3D picking,
  projected brush, sorted original identities, sizing, face keyboard controls and
  continuous colors; 119 frames, **18.83 ms p95**.
- [Workspace](evidence/analysis-refactor/native-workspace.json): separate save
  and restore processes, saved controls and source bytes, no implicit operations;
  **15.19 / 12.08 ms p95**.
- Original million-row × six-feature spawned-worker benchmark, two fits per
  method at existing default sample limits: [PCA](evidence/analysis-refactor/pca-resources.json)
  **767 MiB**, [K-means](evidence/analysis-refactor/kmeans-resources.json)
  **774 MiB**, [t-SNE](evidence/analysis-refactor/tsne-resources.json)
  **751 MiB**, [UMAP](evidence/analysis-refactor/umap-resources.json)
  **938 MiB** combined parent/worker peak upper bounds; all below **2,048 MiB**.
- [Cancellation](evidence/analysis-refactor/cancel-resources.json): confirmed
  worker exit in **0.165 seconds**, no published result.

Native checks use Linux Mesa software OpenGL and preserve source bytes. No
accelerated-rendering or other-platform verification is implied. Existing human
listening and Titanic usability assumptions retain their status.

## Extending and maintaining algorithms

Add a typed parameter dataclass beside its concrete algorithm, using `setting`,
`choice` or field metadata for labels, bounds and conditions. Declare its row and
default limits, implement its family construction/run and any input constraints
or diagnostics, then register it explicitly in `BUILDERS`. Extend the finite
identifier and parameter union/compatibility exports; the GUI and workspace codec
consume the catalog without new method-specific branches. Keep estimator imports
inside worker methods. Fit results retain the existing bounded immutable data
contract; a new prediction capability needs explicit result data and tests.

Import adapters, common Polars preprocessing, stable identity, spawned-worker
ownership/cancellation, analysis settings provenance, plot preparation, pipeline
operations and persistence formats keep their established contracts. The tiny
synthetic feasibility estimators remain independent fixed compatibility probes;
they do not provide production algorithm dispatch or GUI settings. No new methods,
arbitrary estimator plugins, automatic fitting, general out-of-core execution or
new out-of-sample capabilities were added.
