# Analysis package layout

The 2026-10-11 follow-up groups executable methods and legacy compatibility
exports by responsibility. The public catalog continues to enumerate the same
26 concrete classes; method fields, fitting, limits and persisted recipe kinds
remain unchanged. Estimators are imported only when explicitly building/fitting.

## Steps and gates

1. Move method modules into `algorithms/clustering`, `algorithms/decomposition`,
   `algorithms/manifold` and `algorithms/projection`. Their initializers expose
   concrete classes and family unions; `algorithms/__init__.py` exposes abstract
   families, the composed instance type and trusted catalog. Update source,
   test and script callers directly; flat algorithm-module imports are retired.
2. Group the legacy parameter exports into packages. Preserve old parameter
   import names as aliases to the executable classes, together with defaults,
   limits and typed unions. Verify full regression, a built wheel and native
   analysis/session restoration.

The former source-package migration's minimal-initializer convention is replaced
by explicit, cohesive family exports. Avoid wildcard imports and eager estimator
or GUI imports. Public package exports should follow real responsibilities rather
than gather unrelated types into a single root namespace.

## Evidence

Step 1: 181 focused analysis/workspace tests pass, including all-method fitting,
spawned worker publication/cancellation and workspace schema restoration. The
additional fresh-process round-trip test verifies pickled method objects resolve
to the public catalog without importing sklearn, UMAP, Numba or ImGui Bundle.
Pyrefly reports zero errors (one existing suppression and 37 existing warnings);
full Ruff lint/format and diff whitespace checks pass. No GUI behavior changes.
Parameter export grouping and final acceptance are pending.
