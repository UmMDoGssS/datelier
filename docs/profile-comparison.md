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
- [ ] Checklist exclusivity, multiple numeric plots/statistics, arbitrary
  numeric selection count, worker revision lifecycle, and view restore pass.
- [ ] Full suite, Pyrefly, Ruff, native Titanic workflows, and source
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
