# Category distribution relationships

The user clarified that category–numeric relationships should use box/violin
plots. Category–category grouped bars remain in Relationships; single-column
count bars belong in Profiles, where they are already available.

Deliver in two verified steps:

1. Prepare source-aligned numeric distributions per category in workers. Retain
   finite-value exclusions, named missing/Other categories, bounded input and
   seeded density samples, exact cohort quartiles, and immutable plot arrays.
2. Offer Scatter, Box, Violin, and Grouped count bars in Relationships with
   applicable selectors only. Preserve linked selections, sizes, scales, and
   saved views; move older saved single-column count views to Profiles and map
   older numeric aggregate bars to Box.

## Gates

- [x] Distribution correctness, source alignment, edge cases, bounded sampling,
  Pyrefly and Ruff pass.
- [x] Native controls, plots, grouped bars, profile counts, saved-view migration,
  full tests, source preservation and no implicit ML runs pass.

Original Titanic usability gates remain separate from these concrete changes.

Worker evidence: 24 focused tests pass across category distributions, existing
category aggregates, shared distributions and exploration. New cases verify
quartiles/Tukey whiskers and outliers, missing/Other groups, constant and empty
inputs, sorted source-row linking, order-independent seeded density samples,
immutable arrays, the first-100,000-row input cap and 10,000-row selection cap,
extreme scaled coordinates and close large measurements. Pyrefly reports zero
errors; Ruff lint/format pass (199 files). No GUI behavior changes in this step.

## UI and saved-view evidence

Relationships now offers Scatter, Box, Violin, and Grouped count bars only when
the dataset has compatible roles. Box/Violin expose Category and numeric Value;
grouped bars expose Category and a distinct categorical Group by. Scatter's
coordinates, colors and analysis inputs are hidden for the category charts.
Single-column counts remain in Profiles. Legacy count recipes move to Profiles
with their category and height; mean/median/sum recipes open as Box with the
same category/value. New violin recipes retain bandwidth and seed. Legacy
representations remain readable by the recipe codec.

Box/violin charts share the native Expand, Height, Fit axes and numeric Y range/
scale controls. Named categorical X ticks stay categorical. Clicks select the
retained finite rows of the category, capped at 10,000 with a message; grouped
bar clicks retain their existing category/group selection. Density/outlier
sampling is labeled when applicable, and constant groups fall back to box
summaries when density cannot be calculated. Violin outlines close at both ends.

Verified on 2026-10-05 with Titanic (850 rows, 15 columns), Linux and Mesa software
OpenGL:

- `scripts/category_charts_smoke.py`: 201 native frames, a real chart-picker
  click into Box, 430 linked male rows with finite age, 551 rows selected from
  a flat box, and 256-point density curves for both categories. Category–category
  bars retain all 850 rows,
  including Missing, and select the 398 rows in the clicked group. Applicable
  inputs, numeric Y symmetric-log scale and explicit [-10, 90] limits pass.
- `scripts/category_views_smoke.py`: old Count and Mean views and a new Violin
  view save and reopen with their intended routing, columns and 310 px height.
  Violin bandwidth 0.75 and seed 17 survive reopening.
- `scripts/profile_checklist_smoke.py`: all five numeric representations,
  category/numeric exclusivity, two-column statistics and saved selection pass
  in 324 frames. One earlier run missed an injected click after scrolling;
  the repeat passed without an application change.
- Final screenshots of Profiles counts, Box and expanded Violin were inspected.
  Both relationship scripts report zero implicit ML runs and unchanged source
  bytes; the profile regression does too.
- All 483 tests pass. The focused category/workspace suite passes 36 tests.
  Pyrefly reports zero errors; Ruff lint/format pass (201 files). The existing
  untyped SciPy warning and narrowly suppressed HDBSCAN stub issue remain.

Source SHA-256:
`ae179070a631b75d2c3fc7439d624c7fb5e0c8859919dc1d4f96d4d3ed6e854b`.
