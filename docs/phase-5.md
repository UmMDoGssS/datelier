# Phase 5 verification evidence

## M5.1 — Shared flow, PCA and k-means

The shared analysis foundation, PCA GUI/results, and k-means/colors were
implemented as separately verified steps. [Incremental evidence](richer-inspection.md)
records their behavior and checks. PCA and k-means run only by explicit command;
separate numeric features, preprocessing, seed and sample limits are exposed.
Polars handles full-input eligibility and source-ID sampling before bounded
NumPy conversion. Results retain source identity, revision, input/settings,
exclusions/imputation/constants, library versions and runtime.

A background coordinator owns one spawned estimator worker. Cancelling reports
completion only after preparation/worker termination; obsolete revisions cannot
publish. Successful results remain until a revision changes. PCA supports
full/randomized solvers, whitening and 2/3 components. K-means fits sampled
inputs and predicts bounded displayed points using fitted preprocessing/centers,
coloring raw or reduced coordinates without implicitly clustering an embedding.
K-means cluster count caps at 256 to bound prediction distances; legends show
12 leading clusters plus Other and excluded rows. Additional clustering methods
are intentionally not implemented or registered.

Verification (2026-10-04): full suite **264 passed in 12.20s**; batch Pyrefly
zero errors; Ruff lint/format and diff checks passed. Tests cover preprocessing,
source sampling after reorder, PCA subspace/seed behavior, separable clusters
and predictions, parameter rejection, spawned publication/failure/cancellation,
stale revisions, and all six import formats through transformations and linked
analysis plots. The live Linux/Mesa workbench smoke passed **211 frames**,
explicitly running PCA then k-means, checking raw/reduced colors and linked
selection, and preserving source bytes. The final layout/suggestion synchronization
rerun also passed. This uses frame-hook commands; physical analysis-button
clicks are not claimed at this gate.

Eight fresh-parent benchmark runs each fit twice in separately spawned workers:

| Input rows × features | PCA combined peak upper bound | K-means combined peak upper bound |
| --- | ---: | ---: |
| 10,000 × 6 | 246.03 MiB | 251.29 MiB |
| 100,000 × 6 | 277.45 MiB | 281.23 MiB |
| 1,000,000 × 6 | 809.20 MiB | 811.20 MiB |
| 100,000 × 64 | 562.13 MiB | 568.30 MiB |

All pass the declared **2 GiB combined parent/worker budget** with a 10,000-row
fit cap (9,411 eligible rows on the smallest case). Request-to-result times
were 0.666–0.778s; estimator/library initialization time was 0.408–0.464s.
Reports are `docs/evidence/analysis-{pca,kmeans}-{rows}-{features}.json`.
The sum of process high-water marks is a conservative upper bound, including
Linux spawn bootstrap/inherited high-water accounting. The second run warms
filesystem/library caches, not a retained estimator process. Thread settings:
`POLARS_MAX_THREADS=8 OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1`.

M5.1 passes. M5.2, 3D acceptance and final richer-inspection resource gates
remain open. No full-million-row ML fit or unverified rendering/platform
support is claimed.

## M5.2 — t-SNE, UMAP and bounded jobs

t-SNE and UMAP use the verified shared input/job lifecycle. Controls expose
algorithm parameters and resource caps: t-SNE defaults to 2,000 sampled rows
(max 10,000), UMAP to 5,000 (max 50,000). Invalid perplexity, neighbor count,
PCA initialization dimensions, cosine zero vectors, missing inputs and excessive
limits have explicit errors. No import, transform, plotting or setting-change
path implicitly runs an estimator. Worker cancellation and revision invalidation
retain successful current results and prevent abandoned jobs from publishing.

Full suite **267 passed in 12.16s**, Pyrefly zero errors, Ruff lint/format and
diff checks pass. Algorithm fixtures produce finite aligned 2/3-dimensional
embeddings, record exact settings/versions and repeat identically with a fixed
seed on the reference environment. A real t-SNE request is cancelled during
its worker phase with no publication. Failed requests retain previous results.
Live t-SNE and UMAP workbench workflows passed 240 and 1,224 frames respectively,
including linked selection and k-means colors on raw/reduced plots. Runtime
thread limits were also checked without user OMP/BLAS settings. Thread bounds
are applied after estimator imports; the final adjustment passed eight focused
algorithm/job regressions and a fresh GUI check.

Eight fresh-parent cases run each estimator twice in separate workers. Each
case uses a fresh temporary Numba cache for first/warmed-run comparisons.

| Input rows × features | t-SNE combined upper bound | UMAP combined upper bound |
| --- | ---: | ---: |
| 10,000 × 6 | 255.43 MiB | 664.57 MiB |
| 100,000 × 6 | 282.05 MiB | 690.79 MiB |
| 1,000,000 × 6 | 753.02 MiB | 951.81 MiB |
| 100,000 × 64 | 504.45 MiB | 843.94 MiB |

t-SNE wall times were 5.806–8.784s for the 2,000-row sample and 1,000 iterations.
UMAP first runs were 22.44–23.28s and warmed runs 18.65–19.75s for 5,000 rows.
Every combined upper bound passes **2 GiB**. Reports are
`docs/evidence/analysis-{tsne,umap}-{rows}-{features}.json`. These timings include
owned-process startup, library initialization and fitting; they do not promise
interactive fit latency or capacity for full-million-row analysis. First/warmed
fits run in distinct workers, preserving cancellation isolation.

M5.2 passes. Added M5.3 3D and final richer-inspection gates remain open.
