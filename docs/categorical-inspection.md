# Column roles and categorical relationships

The October 2026 follow-up is authorized to broaden Scatter beyond numeric
coordinates and make pair-grid diagonals configurable. Deliver in three steps:

1. Infer roles from types and exact non-null uniqueness in data workers. Unique
   strings are Text; repeated strings are Categorical. Explicit Enum/Categorical
   types stay categorical. Unique integers with ID/index names are Identifier;
   uniqueness alone never excludes a numeric measurement. Schema overrides are
   replayable operations, preserved by undo/redo and workspace recipes. Text and
   identifiers remain in the table/export, but leave automatic profiles, numeric
   feature and color pickers. Focused profiles explain their exclusion.
2. Rename Scatter to Relationships and add categorical counts, category/numeric
   aggregation bars and grouped categorical counts with actual category labels.
   Show only controls applicable to the representation. Preserve numeric 2D/3D,
   decomposition, Colors, plot sizing, and linked selection.
3. Add Histogram/KDE/ECDF/Box/Violin diagonal representation to the correlation
   pair grid, with prepared worker data, saved settings, and named axes.

## Verification gates

- [x] Role inference, reversible overrides, workspace replay, and native Schema
  selection pass. ID heuristics are deliberately conservative; inspect the role
  and override Numeric for an ID-like feature or Identifier for an unnamed ID.
- [ ] Categorical chart preparation and native conditional controls pass,
  including missing values, numeric finite-value exclusion, bounded categories,
  aggregation, and workspace restore.
- [ ] Pair-grid representation preparation, native rendering and saved settings
  pass, with histograms retaining their complete finite-value counts.
- [ ] Full suite, Pyrefly, Ruff lint/format, Titanic GUI and source preservation
  checks pass. No analysis is implicitly launched.

The Titanic source has 850 rows. Its `name` column has 849 distinct non-null
values, so the exact all-unique rule keeps it categorical; use a Text override
if those nearly unique names should be excluded too. Numeric category overrides
allow codes such as `pclass` or `survived` to be represented as categories.

Step 1 evidence: 72 focused tests passed; Pyrefly reported zero errors (the
existing dependency stub suppression remains); Ruff lint and format passed.
`scripts/column_roles_smoke.py` clicked the native passenger ID role dropdown,
selected Numeric and undid it in 61 frames. Feature choices updated, no ML ran,
and the Titanic source SHA-256 stayed unchanged.
