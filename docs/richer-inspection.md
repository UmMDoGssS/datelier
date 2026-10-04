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
