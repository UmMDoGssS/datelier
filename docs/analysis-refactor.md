# Analysis algorithm ownership refactor

Authorized on 2026-10-11: replace algorithm dispatch chains with typed abstract
algorithm families, concrete builders, and dynamically rendered parameter schemas.
Preserve all 26 methods, explicit execution, bounded worker resources, stable row
identity, provenance, prediction capabilities and saved workspace recipes.

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
[Native schemas](evidence/analysis-refactor/native-schemas.json): all 26 forms,
boolean/numeric input, automatic/manual draft retention and conditional fields;
307 frames, 15.22 ms p95. [Native explicit analysis workflow](evidence/analysis-refactor/native-workflow.json):
selector, Run, preserved completion focus and Open result; 220 frames, 15.91 ms
p95. Both preserve source bytes. Catalog/default validation in a fresh process
imports neither sklearn/UMAP/Numba nor the GUI.

Prediction ownership and full acceptance remain open.
