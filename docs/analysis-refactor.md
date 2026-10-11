# Analysis algorithm ownership refactor

Authorized on 2026-10-11: replace algorithm dispatch chains with typed abstract
algorithm families, concrete builders, and dynamically rendered parameter schemas.
Preserve all 26 methods, explicit execution, bounded worker resources, stable row
identity, provenance, prediction capabilities and saved workspace recipes.

Corrected-design acceptance is complete: each concrete algorithm is a single
immutable object with tunable fields, a GUI schema, estimator construction and a
fit facade. The entries below retain the evidence for each
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

## Corrected ownership — authorized 2026-10-11

The user clarified that parameter state and the executable algorithm must be one
object. This supersedes the earlier parameter-record-plus-wrapper design and its
extension instructions. The entries above remain historical acceptance evidence.

### Step 4 — Combine fields and execution

All 26 concrete algorithms are now immutable field-bearing dataclasses. Their
constructor takes tunable fields directly, their schema reflects those fields,
and `fit(prepared)` calls the estimator pipeline. `parameter_type`, the wrapper
constructor and `build_algorithm` are removed. The catalog registers algorithm
classes, application drafts store their instances, and worker dispatch calls the
instance's `fit` method directly. Configuration comparison supports family
polymorphism while still rejecting mismatched fitting/prediction settings.

The workspace codec preserves existing `*Parameters` wire kinds and fields while
constructing the executable algorithm itself. Legacy import names are aliases to
the same class, not separate records. Nothing fits during decoding or restoration.

Verification: **179 focused tests pass**, full Pyrefly **0 errors**, full Ruff
lint/format and whitespace checks pass. A direct facade test fits two and three
clusters from copied configuration, retains the earlier immutable recipe and
preserves row identity. All 26 legacy recipe round-trips and numerical algorithm
checks pass. [Native schemas](evidence/analysis-refactor/unified-native-schemas-step4.json)
verify all 26 forms, primitive input, automatic/manual drafts and conditional
visibility: 381 frames, **15.23 ms p95**. [Explicit analysis](evidence/analysis-refactor/unified-native-workflow-step4.json)
passes selector/Run/Open-result and completion focus: 225 frames,
**15.87 ms p95**. Both preserve source bytes.

Shared fitting simplification and final corrected-design acceptance remain open.

### Step 5 — Shared facades and final acceptance

`DecompositionAlgorithm.fit` and `ClusteringAlgorithm.fit` are the two shared
facades over estimator fitting, transforming or predicting. All concrete methods,
including PCA, t-SNE and UMAP, own their fields and estimator construction while
sharing thread bounds, fit warnings, result validation and provenance. The extra
fitted-decomposition family is removed. UMAP retains its own NumPy/Numba/UMAP
setup and package provenance. Clustering retains the existing nearest-center and
label-only prediction capabilities.

Application drafts explicitly store algorithm instances in `algorithms`.
`AnalysisRequest.method` returns that same executable object; `parameters` is
only the preserved recipe field name. Legacy `*Parameters` import aliases live
in compatibility exports; no algorithm module defines a separate parameter
record or a parameter alias. The finite `AlgorithmInstance` union supplies both
static typing and the catalog, eliminating a second list of registered types.
The [corrected catalog audit](evidence/analysis-refactor/unified-catalog.json)
records all 26 combined objects and their schemas.

```python
method = PCAAlgorithm(solver="full", whiten=True)
request = AnalysisRequest(("x", "y", "z"), method)
result = method.fit(prepare_input(dataset, request))
```

The algorithm's immutable configuration stays separate from the runtime estimator
lifecycle: `fit` constructs and executes its estimator inside the explicit worker
and returns the established bounded result. Fitted estimators are not serialized
into drafts/workspaces. Editing a tunable field creates a new instance through
`with_parameter`, preserving earlier requests and result provenance.

Final corrected-design gates:

- Full pytest: **1,188 passed**, three existing dependency warnings, **33.57 s**.
  All 26 methods, nondefault configurations, row identity, prediction,
  direct fit facade, immutability, legacy recipes and worker lifecycles pass.
  The final application naming cleanup also passes **48 focused settings/recipe
  tests**.
- Full Pyrefly: **0 errors**, the existing one HDBSCAN stub suppression and
  37 warnings. Ruff lint/format (**715 files**), whitespace and evidence links pass.
- [Native schemas](evidence/analysis-refactor/unified-native-schemas.json): all
  26 objects, boolean/real/integer/choice edits, conditional controls,
  automatic/manual retention and no implicit ML; **14.98 ms p95**, 381 frames.
- [Explicit fitting](evidence/analysis-refactor/unified-native-workflow.json):
  features, Run, completion focus and Open result; **16.15 ms p95**, 222 frames.
- [Workspace processes](evidence/analysis-refactor/unified-native-workspace.json):
  save and restore without implicit operations; **24.25 / 10.86 ms p95**.
  All native checks preserve source bytes.
- The original million-row × six-feature worker benchmark, two fits at existing
  default sample limits per method: [PCA](evidence/analysis-refactor/unified-pca-resources.json)
  **757 MiB**, [K-means](evidence/analysis-refactor/unified-kmeans-resources.json)
  **774 MiB**, [t-SNE](evidence/analysis-refactor/unified-tsne-resources.json)
  **754 MiB**, [UMAP](evidence/analysis-refactor/unified-umap-resources.json)
  **943 MiB** combined peak upper bounds; all below **2,048 MiB**.
- [Cancellation](evidence/analysis-refactor/unified-cancel-resources.json):
  confirmed worker exit in **0.163 s**, zero published results.

To extend the implementation, add one immutable concrete algorithm dataclass:
define its tunable fields/metadata, identifier, limits and recipe kind; implement
its estimator construction, input constraints and any special diagnostics or
prediction. Add it to `AlgorithmInstance` and the finite identifier. The catalog,
GUI, requests and workspace codec consume this one definition. Introduce legacy
import aliases only when compatibility requires them. Keep estimator imports and
fitting off GUI frames.

The correction is committed directly on the user's current `main` branch.
Existing Linux Mesa, accelerated-rendering/platform and deferred human usability
or listening assumptions are unchanged. Import adapters, Polars preprocessing,
worker ownership/cancellation, immutable result contracts and recipe formats
retain their established behavior.
