# Unsupervised inspection expansion

The user authorized a broad expansion of unsupervised methods and a Colors
source selector. Methods remain explicit, bounded, revision-bound worker jobs;
no ML runs on selection, import, or workspace restore. Existing scikit-learn
and UMAP dependencies provide the implementations.

## Delivery gates

- [x] Exclusive Colors sources and conditional Column picker.
- [x] Density clustering with distinguishable noise and unassigned rows.
- [x] Additional centroid, mixture, hierarchical and graph clustering.
- [x] Additional linear and manifold embeddings, in 2D and 3D.
- [ ] Full correctness suite, Titanic GUI workflow and saved recipe round trips.

## Colors source controls

Uniform, Column and K-means are always available; only Column shows a column
picker. Clustering has its own explicit setup/Run controls, including before
any result exists. Results color raw coordinates and embeddings independently.
Selecting Uniform while a job runs retains Uniform after completion. Workspaces
save the source choice without fitted artifacts; older saved column colors
restore as Column. Dataset revision changes invalidate fitted colors.

Verification: 40 focused analysis/workspace tests pass; Pyrefly reports zero
errors; Ruff lint/format pass. Linux/Mesa live GUI checks pass for hidden Analysis
navigation without fitting (42 frames) and explicit 3D PCA/K-means, colors on raw
and embedded axes, linked selection and source preservation (219 frames).
Remaining method gates are open.

## Density clustering

DBSCAN exposes radius, minimum neighbors and distance; HDBSCAN exposes minimum
cluster size/neighbors, hierarchy selection and optional single-cluster output;
OPTICS exposes minimum size/neighbors, steepness and distance. Caps are 5,000 /
10,000 / 5,000 fitting rows, with defaults of 2,000. Noise (-1) has a separate
color/legend from unassigned/excluded (-2). Label-only methods color fitted
identities, without invented predictions for unseen rows. Warnings, counts,
settings, input summary and library versions remain available in provenance.
New method records round-trip through the strict registered recipe codec.

Verification: 56 focused density/input/analysis/workspace tests pass (11.57 s),
including repeatability, sample identity alignment, separate noise/unassigned
colors and invalid settings. Pyrefly reports zero errors with one narrow
HDBSCAN stub omission suppression (the installed public API is present); Ruff
lint/format pass (166 files). Linux/Mesa GUI checks render all parameters, click
Run before any fit, color raw 3D axes and preserve linked selection/source data:
DBSCAN 141 frames, HDBSCAN 138 frames, OPTICS 141 frames. The final layout was
visually inspected. Clustering outcomes depend on settings; OPTICS/HDBSCAN need
not identify the same noise or clusters as DBSCAN. Remaining gates stay open.

## Additional clustering

Eight more methods are available in Colors: Mini-batch K-means, Gaussian
mixture, Bayesian Gaussian mixture, Agglomerative, Birch, Mean shift, Spectral
clustering and Affinity propagation. Count-based methods reject more requested
clusters than distinct sampled inputs. Mixtures expose covariance and
regularization; Bayesian mixtures also expose weight concentration. Mean shift
has automatic/manual bandwidth, with the fitted bandwidth in provenance.
Spectral affinity switches between neighbors and kernel gamma. Affinity
propagation has automatic/manual preference; a fit with no assignments fails
clearly. Empty mixture components are compacted into occupied labels.

Mini-batch K-means retains nearest-center prediction for displayed rows. Other
new methods show assignments only for known fitting identities. Caps: mini-batch
and Birch 100k, mixtures 50k, agglomerative/mean shift 5k, spectral 3k, affinity
propagation 2k. Defaults are 10k for fast methods and 2k otherwise. These are
execution bounds, not capacity guarantees.

Verification: 70 focused clustering/input/analysis/workspace tests pass (10.20 s),
including deterministic grouping, row alignment, sample caps, unseen assignments
and distinct-input failures. Pyrefly reports zero errors (the existing narrow
HDBSCAN stub suppression remains); Ruff lint/format pass (167 files). All eight
methods pass live Linux/Mesa parameter rendering, actual Run clicks, raw 3D
colors, linked selection and source preservation (135–151 frames per method).
The default affinity preference can produce more exemplars than intuitive
blobs; the grouping test checks cluster purity rather than imposing a fixed
cluster count on this method. Embedding and final milestone gates remain open.

## Linear and factorization views

Coordinates now includes Truncated SVD, FastICA, Factor analysis, Kernel PCA,
NMF, Gaussian random projection and Sparse random projection. All support
explicit 2D/3D fitting, seed/settings provenance and linked source identities.
SVD exposes power iterations; ICA exposes contrast/iterations/tolerance; factors
expose rotation/iterations/tolerance; kernel PCA exposes kernel with conditional
gamma/degree. NMF exposes minmax/none input scaling and rejects negative input
when scaling is disabled. Minmax normalizes magnitudes before computing ranges
to avoid overflow, and records the [0, 1] transformation in the fit details.
Random projections use explicit output dimensions and seed; sparse projections
also expose density.

Caps: SVD/projections 100k, ICA/factors/NMF 50k, kernel PCA 3k; defaults 10k except
kernel PCA 2k. Fitting dimension/rank and NMF domain checks run before estimator
execution. Parameter families and coordinate result validation have their own
modules; no new dependencies were needed.

Verification: 55 focused linear/workspace tests pass (1.07 s), including both
dimensions, repeatability, finite immutable coordinates, unchanged prepared
inputs, source-ID/position alignment, NMF domain/scaling and dimension failures.
Pyrefly reports zero errors; Ruff lint/format pass (172 files). All seven methods
pass Linux/Mesa live settings, explicit Run clicks and linked 3D inspection
(135–142 frames each). The manifold and final milestone gates remain open.

## Manifold views

Isomap, metric/nonmetric MDS, Spectral embedding and Locally linear embedding
complete the catalog of 26 methods (12 clustering, 14 coordinate methods). LLE
additionally offers standard, modified, Hessian and LTSA variants. Neighbor/row
and Hessian rank constraints fail before fitting. Isomap and LLE use bounded
dense eigensolving; LLE's 2k cap avoids unbounded dense work and singular ARPACK
neighborhood failures. MDS exposes initialization, relevant initialization
count, iterations and stress tolerance. Spectral affinity exposes either
neighbors or gamma. Warnings and stress/reconstruction diagnostics are recorded.
Caps: Isomap 3k, MDS 2k, Spectral embedding 5k, LLE 2k; defaults 2k.

Verification: 86 focused manifold/linear/input/workspace tests pass (2.99 s),
including both dimensions, all LLE variants, both MDS types, spectral affinities,
repeatability and neighborhood failures. Pyrefly reports zero errors; the
installed MDS 1.9 constructor is isolated behind a narrow typed boundary because
its bundled stubs still describe the older API. Ruff lint/format pass (174
files). Four Linux/Mesa GUI checks pass live forms, actual Run clicks and linked
3D views (135–143 frames). Titanic and final full-suite gates remain open.

## Final control and restore fixes

Unfitted clustering setup starts collapsed in Scatter, leaving the raw plot and
Run button visible. The full controls remain in Analysis and can be opened
inline. Opening an embedding's setup while cluster colors are selected now
focuses that embedding in Analysis; source changes and completed embeddings
update the panel context. Changing embedding dimensions no longer claims that a
clustering fit is stale. Removing a selected color column immediately binds
Column mode to an available column before plot preparation.

All 26 setting records now pass a full registered-codec Workspace round trip,
including non-default DBSCAN/LLE settings and unfitted source choices. Tests
verify completed clustering cannot overwrite Uniform/Column and revision
changes clear fitted colors. Nineteen focused control/worker tests pass
(2.94 s); Pyrefly and Ruff lint/format pass. Native Linux/Mesa checks pass hidden
Analysis navigation with simultaneous clustering/embedding sources (42 frames),
3D PCA/K-means linked colors (213 frames), and save/relink/restore/redo/2D linked
selection with DBSCAN/LLE settings and zero implicit fits (31/45 frames).
The original Titanic exclusive-coordinate GUI check also passes (165 frames).
