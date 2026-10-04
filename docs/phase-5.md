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

M5.1 passes; subsequent gates are recorded below. No full-million-row ML fit or unverified rendering/platform
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

M5.2 passes; final M5.3 evidence follows.

## M5.3 — 3D and final live acceptance

Raw XYZ and three-component PCA/t-SNE/UMAP views use bundled ImPlot3D, with
identity-aligned column/k-means colors, projected picking and screen-space Shift
brushing. Camera rotation/pan/zoom remain available and brushing locks camera
gestures. Two-component results never silently refit to supply Z. The shared
clustering record now carries optional fitted k-means artifacts; label-only
results can retain identity without a prediction contract. No additional
clustering algorithm, public registry or persistence schema was introduced.

Final full suite **271 passed**, Pyrefly zero errors, Ruff lint/format,
lock and diff checks pass. [Final inspection evidence](richer-inspection.md#step-8--final-workflow-and-resource-acceptance)
records live controls/gesture checks, visually inspected screenshots and eight
large/wide GUI measurements. Every inspection case passes **33ms frame p95**
and **1GiB parent RSS** with bounded displayed points and source preservation.
The final 3D benchmark additionally verifies visible selected marker pixels.

All four default algorithms also run explicitly, sequentially, in fresh live
GUI parents with the source table still open:

| Source rows × numeric analysis features | GUI frame p95 | Parent peak | Worker peak | Combined upper bound |
| --- | ---: | ---: | ---: | ---: |
| 1,000,000 × 6 | 16.82 ms | 725.95 MiB | 725.95 MiB | 1,451.90 MiB |
| 100,000 × 64 | 17.71 ms | 691.82 MiB | 691.82 MiB | 1,383.64 MiB |

Both pass **2GiB combined parent/worker RSS** and the frame budget. Limits are
10,000 rows for PCA/k-means, 2,000 for t-SNE and 5,000 for UMAP. Reports:
[million-row GUI](evidence/analysis-live-large.json),
[wide GUI](evidence/analysis-live-wide.json), and
[screenshot](evidence/analysis-live-wide.png). These runs did not set user
OMP/BLAS thread limits; runtime estimator limits apply. Live request-to-result
times were 1.28s PCA, 1.43–1.46s k-means, 9.15–14.04s t-SNE and 31.56–32.91s
UMAP, including background input and display preparation. The separate
first/warmed worker reports in M5.1/M5.2 remain the cold/warm timing evidence.
Process high-water sums conservatively include inherited spawn accounting;
identical parent/worker peaks are not simultaneous-live-memory measurements.

Four separate million-row requests cancel after worker startup, during the
reported combined library-loading/fitting phase. Cancellation-to-confirmed-exit
was **0.121–0.172s**, with zero results published; estimator iteration progress
was not observed. Reports are `evidence/analysis-cancel-{pca,kmeans,tsne,umap}.json`.
The lifecycle tests additionally reject failures, obsolete revisions and a
cancel arriving after worker exit but before GUI publication. Preparation cannot
be forcibly interrupted; cancellation waits for preparation or terminates and
joins the owned worker before reporting stopped.

Reproduction on the Linux graphical session:

```sh
POLARS_MAX_THREADS=8 uv run scripts/benchmark_exploration.py
LIBGL_ALWAYS_SOFTWARE=1 POLARS_MAX_THREADS=8 uv run scripts/benchmark_exploration.py --gui 100000 64 --three-d --output /tmp/rich-3d.ppm
LIBGL_ALWAYS_SOFTWARE=1 POLARS_MAX_THREADS=8 uv run scripts/benchmark_exploration.py --gui 100000 64 --view grid --output /tmp/rich-grid.ppm
LIBGL_ALWAYS_SOFTWARE=1 POLARS_MAX_THREADS=8 uv run scripts/benchmark_analysis_gui.py --rows 1000000 --columns 6 --output /tmp/analysis-gui.ppm
POLARS_MAX_THREADS=8 uv run scripts/benchmark_analysis.py --algorithm tsne --cancel --output /tmp/analysis-cancel.json
```

M5.3 and Phase 5 pass. Linux/Mesa remains the verified renderer; accelerated
rendering and other platforms remain unverified. User-raised sample caps were
validated as bounds, not benchmarked as capacity guarantees. Workspaces remain
Phase 6. Spectral, agglomerative, DBSCAN and HDBSCAN remain future additions.
