# Richer inspection and analysis implementation evidence

The authorized delivery extends the passed Phase 4 baseline with numeric
comparisons, independent raw axes/coloring, relationship heatmaps/grids, and
Phase 5 on-demand analysis plus 3D views. Workspace persistence remains Phase 6.
K-means is the only clustering method in this delivery.

## Step 1 — Numeric comparisons

Implemented up to eight numeric columns, shared-bin count/density histograms,
Scott-bandwidth Gaussian KDE with multiplier, sampled ECDF, exact Polars box
statistics, and side-by-side violin plots. Original units and optional z-scores
are explicit. Source-ID/seed sampling caps each density/ECDF cohort at 2,000;
box outliers cap at 150. Empty/constant/nonfinite and overflowing raw ranges
have explicit outcomes. Existing categorical/temporal profiles remain available.
SciPy is now an explicit locked dependency.

Verification: 15 focused tests passed; batch Pyrefly reported zero errors;
Ruff lint/format and diff whitespace passed. `scripts/comparison_smoke.py`
rendered all five modes in 83 Linux/Mesa frames. Its final screenshot was
visually inspected. This is a frame-hook renderer check, not a physical-input
claim. Final milestone/resource gates remain open.

## Step 2 — Raw axes and column coloring

Raw X/Y and color selectors are now visible in Scatter, independent of profile
controls. Prepared per-point colors support continuous numeric/temporal scales
and deterministic top-12 categorical/Boolean legends with Other and missing.
Temporal colors shift in integer space, preserving close nanosecond values.
Source positions and IDs remain aligned after sorting; selections override
colors visibly. Compact controls and expandable legends/help keep the plot usable.

Verification: 15 focused coloring/exploration/selection/plot tests passed;
Pyrefly zero errors; Ruff lint/format and diff checks passed. The live comparison
smoke now also exercises a colored raw scatter and table-linked highlight
(116 frames initially, final layout rerun recorded in command output).

## Step 3 — Relationship heatmap and grid

Explicit ordered numeric features drive a fixed −1…+1 Pearson heatmap with
undefined cells colored gray and finite-pair tooltips. Heatmap clicks navigate
to raw axes or profiles. The grid caps features at eight and each pair at 150
points drawn from the common 10,000-row correlation cohort. Mirrored cells
reuse coordinates and source IDs; current table positions are mapped correctly.
Diagonal exact histograms disclose their bin-index axes and link to profiles.
Heatmap expansion to 16 features does not prepare an oversized grid.

Verification: 13 focused relationship/exploration/all-format workflow tests
passed; Pyrefly zero errors; Ruff lint/format and diff checks passed. The live
relationship smoke passed 60 frames, including injected mouse navigation from
a heatmap cell and linked grid highlights. Final grid screenshot inspected.

## Step 4 — Shared analysis foundation

Typed requests cover explicit features, algorithm parameters, preprocessing,
seed and bounded samples. Polars handles full-column eligibility; only the
bounded matrix becomes NumPy. Stable source-ID hashing preserves cohorts after
reordering. Preprocessing reports exclusions, imputed cells, constant features
and retained inputs, with overflow-resistant standardization and fitted state.
A background coordinator prepares inputs and owns one spawned worker. Cancellation
waits for preparation or terminates/joins that worker; revision checks reject
obsolete results and errors cannot overwrite successful results.

Verification: 12 focused preparation and actual spawned-process lifecycle tests
passed; Pyrefly zero errors; Ruff lint/format and diff checks passed. No GUI
behavior changes in this foundation step. Algorithm runners and milestone
acceptance remain open until their subsequent verified steps.

## Step 5a — PCA and explicit analysis GUI

PCA runs in the worker with full/randomized solver, whitening, 2/3 dimensions,
seed, preprocessing and sample limits. Completed coordinates and library/runtime
provenance are immutable and revision-bound. A separate docked Analysis panel
selects features independently of visible raw X/Y. Scatter switches between raw
and completed embeddings without refitting; embedding preparation/colors run
in a background job. Explicit completion opens the scatter view. Changing
settings marks the retained result as needing an explicit rerun.

Verification: 19 focused preparation/job/PCA/all-format exploration tests passed;
known PCA subspace, seed repeatability, three components, bounded plots and source
alignment pass. Pyrefly zero errors; Ruff lint/format and diff checks passed.
The live PCA workbench smoke passed 109 frames before the final label adjustment;
its final rerun passed and the embedding/linked-table screenshot was inspected.
M5.1 remains open until k-means and resource/workflow acceptance pass.

## Step 5b — K-means and M5.1 acceptance

K-means results retain labels/IDs, fitted preprocessing, centers, counts and
inertia. Bounded display predictions color raw and reduced scatters independently
of their axes. Legends distinguish fitting cohorts, predictions, Other and
excluded rows. The GUI exposes settings/centers and preserves raw-axis choices.
Suggested-pair navigation now synchronizes those independent selectors.

Full suite: 264 passed; Pyrefly/Ruff/diff checks pass; 211-frame live workflow
plus final layout rerun pass. Eight resource runs pass the 2 GiB combined budget,
including million-row and 64-feature inputs with a 10,000-row fit cap.
[M5.1 evidence](phase-5.md) records measurements and limitations. M5.1 passes.

## Step 6a — t-SNE

t-SNE now exposes perplexity, iteration count, auto/explicit learning rate,
PCA/random initialization, dimensions, seed, preprocessing and capped samples.
It runs only by command in the owned worker; results record KL divergence,
completed iterations and fixed Euclidean/Barnes-Hut settings. Estimator/BLAS
thread pools are explicitly limited to one using the newly direct locked
threadpoolctl dependency. Controls and result-view integration were separated
when the combined GUI module approached the contributor review threshold.

Verification: 15 focused preparation/job/algorithm tests pass, including finite
2/3-dimensional t-SNE and same-seed repeatability; Pyrefly zero errors;
Ruff lint/format and diff checks pass. The live `--reduction tsne` workflow
runs t-SNE explicitly, selects linked rows and applies k-means colors to raw
and reduced points. Final M5.2 resource/acceptance gates remain open.

## Step 6b — UMAP and M5.2 acceptance

UMAP exposes neighbors, minimum distance and Euclidean/cosine metric in addition
to common features/preprocessing/dimensions/seed/sample limits. It uses recorded
spectral initialization, low-memory mode and one estimator/Numba thread.
Library warnings are retained in result provenance. Estimator thread bounds
are applied after imports so newly loaded OpenMP/BLAS libraries are covered.

Full suite: 267 passed in 12.16s; final thread-bound adjustment passed eight
focused algorithm/job regressions; Pyrefly/Ruff/diff checks pass. The live UMAP
workflow passed 1,224 frames with explicit execution, linked embedding and
raw/reduced cluster colors. A t-SNE GUI rerun without OMP/BLAS environment
settings verifies runtime thread limits. All eight t-SNE/UMAP resource runs
pass the 2 GiB combined budget. [M5.2 evidence](phase-5.md#m52--t-sne-umap-and-bounded-jobs)
records first/warmed worker timings. M5.2 passes; 3D/final inspection gates remain open.

## Step 7 — Raw and reduced 3D plots

ImPlot3D is enabled in the workbench. Raw XYZ eligibility excludes invalid values
across all three axes; reduced plots use an explicitly fitted third component.
A two-component result cannot silently refit when 3D is selected. Column and
cluster colors use the same prepared identity-aligned arrays. Projected picking
uses an eight-pixel radius and frontmost ray-depth ties; Shift brushing selects
projected displayed rows and locks camera gestures during the brush. Camera
rotation drags do not become point selections. Active-item hover handling was
corrected after the first live input check caught missed clicks.

Verification: 16 focused 3D/algorithm/selection/relationship/exploration tests
passed; Pyrefly zero errors; Ruff lint/format and diff checks passed. Final live
runs passed **141 frames** of sorted-source picking, Shift brushing, rotation,
wheel zoom and right pan, and **208 frames** of explicit three-component PCA,
linked selection and raw/reduced k-means colors. Screenshots were visually
inspected: [gestures](evidence/scatter3d-gestures.png) and
[analysis colors](evidence/analysis-3d-workbench.png). The frame hooks inject
Dear ImGui mouse/key events and position the backend cursor for the gesture run.
M5.3/final extension gates remain open pending large/wide resource acceptance.

## Step 8 — Final workflow and resource acceptance

Completed the inspection and analysis gates on 2026-10-04. Final acceptance
found and corrected three performance/lifecycle issues: overlapping KDE jobs
now serialize their short BLAS evaluations with one thread; linked selections
cache bounded partitions per displayed plot instead of rebuilding every grid
cell each frame; and 3D uses compact filled squares without outline strokes.
Native item colors remain opaque, because transparent outlines also disabled
fills in the bundled renderer. The large/wide 3D benchmark now checks visible
orange marker pixels in addition to selection identity and frame timing.

Comparison histograms now render shared-bin steps, outlier sampling is explicit,
and counts/sample details expand without pushing the comparison offscreen.
Dense grids use numbered outer axes with an ordered feature key and full-name
hover text; their plots remain scrollable. Failed scatter preparation leaves
axes/colors and completed embeddings accessible for correction. Clustering
results separate optional k-means fitted artifacts from common labels/identity;
a label-only result colors known IDs and leaves unseen rows unassigned.
Cancellation after worker completion but before GUI polling cannot publish.

Final full suite: **271 passed**; batch Pyrefly zero errors, Ruff lint/format,
locked dependency resolution and diff whitespace pass. New regressions cover
alternating linked views, selection/revision invalidation, label-only assignments,
and cancellation at the publication boundary. Final live checks passed 131
frames of all five profile modes, colored selection and error recovery; 60
frames of heatmap navigation/grid highlights; 141 frames of 3D picking/brushing,
rotation, wheel zoom and right pan; and 267/1,349 frames of explicit three-component
t-SNE/UMAP with linked raw/reduced k-means colors. One injected-cursor rotation
check missed its gesture; a fresh run passed all gestures. Native analysis-button
clicks and overlay-legend clicks are not claimed by these frame-hook scripts;
the native selectable legends rendered and their screenshots were inspected.

Four fresh headless fixtures pass the retained summary/page/inspection budgets:

| Rows × total columns | Default preparation | Numeric comparison | Expanded preparation | Peak RSS |
| --- | ---: | ---: | ---: | ---: |
| 10,000 × 8 | 22.42 ms | 53.60 ms | 11.06 ms | 196.33 MiB |
| 100,000 × 8 | 24.76 ms | 77.71 ms | 19.04 ms | 244.02 MiB |
| 1,000,000 × 8 | 125.20 ms | 317.98 ms | 60.55 ms | 680.03 MiB |
| 100,000 × 66 | 54.85 ms | 105.10 ms | 46.29 ms | 517.73 MiB |

Default preparation remains bounded by 2s; expanded/comparison preparation by
4s. Measured summaries remain below 250ms, pages below 50ms, and bounded linked
interaction p95 below 2.13ms. The [fresh-process report](evidence/richer-inspection-benchmark.json)
records CPU, memory, versions, fixture types and exact observations. Its samples
do not fit or render one million points.

Eight live GUI cases sort/filter the original table, retain source IDs, select
10,000 sampled rows and render bounded table pages. Grid/comparison configurations
select up to eight features; wide grids render all 56 off-diagonal cells with
at most 150 points each. Narrow fixtures contain seven numeric features.

| View | Million-row frame p95 / peak RSS | Wide frame p95 / peak RSS |
| --- | ---: | ---: |
| 2D scatter | 21.32 ms / 680.11 MiB | 22.17 ms / 644.43 MiB |
| 3D scatter | 28.37 ms / 734.32 MiB | 28.07 ms / 645.81 MiB |
| Pair grid | 16.66 ms / 686.07 MiB | 16.70 ms / 645.22 MiB |
| KDE comparison | 15.93 ms / 820.21 MiB | 15.95 ms / 657.89 MiB |

All pass **33ms frame p95** and **1GiB inspection RSS**. Reports are
`evidence/richer-{large,wide}-{2d,3d,grid,comparison}.json`. Final screenshots
were visually inspected: [comparison](evidence/richer-wide-comparison.png),
[grid](evidence/richer-wide-grid.png), [2D](evidence/richer-wide-2d.png),
[3D](evidence/richer-wide-3d.png), and [3D gestures](evidence/scatter3d-gestures.png).
Initial circular 3D markers exceeded the frame budget (~188ms); final compact
square rendering passes without reducing the 10,000-point display bound.

The [Phase 5 final evidence](phase-5.md#m53--3d-and-final-live-acceptance)
records combined live-GUI/worker resources and cancellation timings. M4.3 and
M5.3 pass; Phase 5 is complete. Verified rendering remains Linux/Mesa software
OpenGL on this machine. Accelerated rendering and other platforms are unverified;
sample caps are not capacity guarantees. Workspace persistence remains Phase 6.
