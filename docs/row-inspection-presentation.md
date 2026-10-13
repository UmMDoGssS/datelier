# Row inspection presentation — authorized 2026-10-13

The requested follow-up makes Inspect a detailed row browser for all types,
with all columns shown by default and a retained column selector. Gallery rows
use separate name/value tables; focused records use ruled column titles and
highlighted values. Preview and Inspect share value colors. Profiles use one
row per column and one column per statistic, with deterministic separated plot
hues for the displayed series.

## Verified steps

- [x] Preview colors: opaque white null cells with bold black text, including
  selected rows; original Unicode Text lengths use interpolated Viridis with
  the existing percentile/linear/custom scale controls. Categories keep their
  categorical palette. Shading remains a display-only setting.
- [ ] Inspect: all selected columns, shared styling, separated gallery tables,
  ruled focused fields, lazy media previews and retained detailed tools.
- [ ] Profiles: wide statistics tables and separated saturated comparison hues.
- [ ] Full-suite and native acceptance.

Step 1 checks: `uv run pyrefly check` (zero errors), eight focused tests in
`test_table_presentation.py`, `test_profile_preview.py`, `test_rebuild_table.py`,
Ruff lint/format and diff whitespace pass. Native Mesa Dark and Light smoke
checks pass (31 frames each), verifying an opaque null background and a loaded
bold font in rendered preview cells. Screenshots/reports are generated under
`/tmp/datelier-row-inspection` by `scripts/rebuild_row_inspection_smoke.py`.
The display check runs outside the sandbox to access the Linux display socket.
Existing platform, accelerated-rendering, listening and usability assumptions
retain their status.
