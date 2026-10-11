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

## Imports

```python
from datelier.analysis.algorithms import ALGORITHMS, AlgorithmInstance
from datelier.analysis.algorithms.clustering import KMeansAlgorithm
from datelier.analysis.algorithms.decomposition import PCAAlgorithm
from datelier.analysis.algorithms.manifold import UMAPAlgorithm
from datelier.analysis.algorithms.projection import SparseProjectionAlgorithm
```

Legacy `datelier.analysis.parameters` now has a `clustering` package;
`datelier.analysis.embedding_parameters` has `decomposition`, `manifold` and
`projection` packages. Both top-level initializers preserve the old parameter
aliases, unions, defaults and limits. These aliases are the same executable
classes; they introduce no distinct parameter objects or new behavior. Defaults
are derived from the typed unions rather than maintaining duplicate method lists.
The four original parameter aliases in `analysis.types` remain compatible.

## Evidence

Step 1: 181 focused analysis/workspace tests pass, including all-method fitting,
spawned worker publication/cancellation and workspace schema restoration. The
additional fresh-process round-trip test verifies pickled method objects resolve
to the public catalog without importing sklearn, UMAP, Numba or ImGui Bundle.
Pyrefly reports zero errors (one existing suppression and 37 existing warnings);
full Ruff lint/format and diff whitespace checks pass. No GUI behavior changes.

Step 2 and final acceptance: [verification](evidence/analysis-packages/verification.json)
records **1,190 passing tests** (three existing dependency warnings), zero Pyrefly
errors and passing Ruff lint/format and whitespace checks. The legacy alias test
verifies all 22 extra-method names/defaults/limits and all 11 legacy embedding
names still refer to the catalog's executable objects and round-trip saved recipes.
The [wheel check](evidence/analysis-packages/wheel.json) verifies all 26 recipes
using code extracted from the newly built wheel in an isolated Python process,
with no ML or GUI imports. No new dependency installation was required.

Serial Linux Mesa native checks pass:

- [All 26 forms](evidence/analysis-packages/native-schemas.json): 381 frames,
  p95 15.265 ms, native field edits, automatic/manual draft retention and
  conditional visibility; no implicit analysis, source preserved.
- [Feature selection / Run / Open result](evidence/analysis-packages/native-workflow.json):
  220 frames, p95 15.931 ms, completion preserves focus and source bytes.
- [Separate-process save/restore](evidence/analysis-packages/native-workspace.json):
  24 save and 31 restore frames, p95 25.605 / 11.349 ms; source preserved and
  zero implicit operations.

The flat algorithm-import audit finds no stale callers in source, tests or scripts.
Method modules moved without changing their numerical implementations. Resource
benchmarks are unchanged; this follow-up verifies packaging and workflows and
makes no new capacity, accelerated-rendering or platform claims. All listed
package reorganization gates pass.
