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
- [ ] Native controls, plots, grouped bars, profile counts, saved-view migration,
  full tests, source preservation and no implicit ML runs pass.

Original Titanic usability gates remain separate from these concrete changes.

Worker evidence: 24 focused tests pass across category distributions, existing
category aggregates, shared distributions and exploration. New cases verify
quartiles/Tukey whiskers and outliers, missing/Other groups, constant and empty
inputs, sorted source-row linking, order-independent seeded density samples,
immutable arrays, the first-100,000-row input cap and 10,000-row selection cap,
extreme scaled coordinates and close large measurements. Pyrefly reports zero
errors; Ruff lint/format pass (199 files). No GUI behavior changes in this step.
