# Unsupervised inspection expansion

The user authorized a broad expansion of unsupervised methods and a Colors
source selector. Methods remain explicit, bounded, revision-bound worker jobs;
no ML runs on selection, import, or workspace restore. Existing scikit-learn
and UMAP dependencies provide the implementations.

## Delivery gates

- [x] Exclusive Colors sources and conditional Column picker.
- [ ] Density clustering with distinguishable noise and unassigned rows.
- [ ] Additional centroid, mixture, hierarchical and graph clustering.
- [ ] Additional linear and manifold embeddings, in 2D and 3D.
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
