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
