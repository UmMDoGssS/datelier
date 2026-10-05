# Schema and profile comparisons

The user requested exact Schema counts, statistics below profile plots, and a
checklist allowing one categorical column or any number of numeric columns.
Deliver and verify these coherent steps separately:

1. Schema shows `Column`, `Non nulls`, `Uniques`, `Type`, and `Interpretation`,
   with `Shape: (cols, rows)` above. Non-null and unique counts exclude nulls;
   NaNs and infinities are still non-null values. Role overrides remain usable.
2. Prepare numeric statistics in workers and display a table below the plot.
   Moments and quantiles use finite values, standard deviation uses ddof=1,
   and float modes round to two decimal places. Report nulls, NaNs, and total
   non-finite values separately. Undefined statistics display a dash.
3. Replace the single-column dropdown and separate comparison workflow with a
   checklist. Numeric selections share colored distribution plots and legends,
   and each selected column has a statistics row. Category selection is
   exclusive. Preserve plot sizing, scales, representations, and saved views.

## Verification gates

- [x] Schema counts and native role override/undo are verified.
- [x] Statistics correctness, finite-value handling, and native table layout
  below the plot are verified.
- [x] Checklist exclusivity, multiple numeric plots/statistics, arbitrary
  numeric selection count, worker revision lifecycle, and view restore pass.
- [x] Full suite, Pyrefly, Ruff, native Titanic workflows, and source
  preservation pass, with no implicit analysis runs.

Original Titanic usability gates remain separate from this follow-up.

Schema evidence: four role-inference tests, Pyrefly (zero errors), Ruff lint and
format pass. The native Titanic Schema check passed in 61 frames, including a
real role dropdown selection and undo. All five headings fit the default pane;
shape is `(15, 850)`, `age` has 676 non-null rows and 88 uniques. The source is
unchanged and no analysis ran. Screenshot: `/tmp/datelier-column-roles.png`.

Statistics evidence: 22 focused profiling, statistics, exploration, and preview
tests pass, including empty/constant columns, Float64 overflow, literal column
names, rounded/tied modes, and integer extrema above 2**53. Pyrefly has zero
errors and Ruff lint/format pass. Native Titanic age Histogram and expanded KDE
checks, plus sex counts, pass with source preservation. The expanded view keeps
statistics below the plot; narrow tables scroll horizontally with the column
name frozen. Mean/std/median/mode for age are 29.5198/14.5622/28/18. Screenshot:
`/tmp/datelier-profile-statistics.png`.

Checklist evidence: 45 focused tests passed before final hardening. Explicit
selection of 140 numeric columns prepares all 140 statistics rows and shared
distributions, beyond both the old eight-column comparison and 128-column
automatic-profile caps. Automatic preparation remains bounded; explicit
selection grows linearly with column count. Curves remain capped at 2,000 finite
values per column. This is not a capacity guarantee for arbitrary dataset sizes.
Tests cover category exclusivity, intentional empty selections, name/role
changes, source-unit statistics with z-score plots, recipe compatibility, errors,
revision changes, abandoned results, and worker closure.

The native Titanic checklist check passed in 324 frames: real checkbox clicks
for age/fare, replacement with sex, replacement back to numerics, all five
representations, two matching-color statistics rows, and preferences reopening.
Popup constraints prevent auto-size shrinking during virtualized scrolling.
Single and shared plots pass actual drag/expand/restore and Axes/Apply clicks,
including range and scale preservation (118 frames each). Native date and
all-null profiles pass. Correlation diagonals still pass all five representations
and workspace reopening (144/23 frames). Fresh-process preferences and workspace
relink/redo/selection checks pass. The workspace check exposed a pending-state
race that reset Pair grid for a legacy default-feature recipe; both its focused
regression test and native restore now pass.

Final verification: **470 tests passed in 15.63 s**, Pyrefly zero errors (one
pre-existing dependency-stub suppression), Ruff lint/format pass (196 files),
and clean diff whitespace. No ML runs were implicit. Titanic's SHA-256 remains
`ae179070a631b75d2c3fc7439d624c7fb5e0c8859919dc1d4f96d4d3ed6e854b`.
Screenshot: `/tmp/datelier-profile-checklist.png`.

Counts and numeric statistics use all retained rows. Numeric moments,
quantiles, and curves use Float64 coordinates; extreme unrepresentable results
display a dash, and a shared-range failure retains statistics and the available
single-column scaled histogram. Category counts/mode use the first 100,000 rows
when needed, with a visible sample label. Date profiles remain single selections.
Stats stay in the expanded plot window; narrow tables scroll with names frozen.
