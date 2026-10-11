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
