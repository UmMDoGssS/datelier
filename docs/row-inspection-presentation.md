# Row inspection presentation — authorized 2026-10-13

The requested follow-up makes Inspect a detailed row browser for all types,
with all columns shown by default and a retained column selector. Gallery rows
use separate name/value tables; focused records use ruled column titles and
highlighted values. Preview and Inspect share value colors. Profiles use one
row per column and one column per statistic, with deterministic separated plot
hues for the displayed series.

## Verified steps

- [x] Preview colors: opaque white null cells with bold black text, including
  selected rows; original Unicode Text lengths use interpolated Crest with
  the existing percentile/linear/custom scale controls. Categories keep their
  categorical palette. Shading remains a display-only setting.
- [x] Inspect: all selected columns, shared styling, separated gallery tables,
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

Step 2 checks: 52 focused record/nested/gallery/image/table tests, Pyrefly,
Ruff lint/format and diff whitespace pass. Native gallery and focused layouts
pass in Dark and Light (51 frames each); focused rows show both image columns
through the shared bounded preview cache. The existing array-gallery native
gate passes sorted source-row opening and exact pixels: first visible preview
73 ms, peak shared GPU retention 42,848 bytes, at most two uploads/pending
array jobs, no collection analysis or playback, source preserved. Native
original image/text/audio tools pass with explicit shown-column selection.
The record-family harness now selects the tools column so native commands
remain visible in the new source-order row layout.

The user replaced Viridis with Crest during this step. Its light-green to
dark-blue samples come from [Seaborn's palette data](https://github.com/mwaskom/seaborn/blob/v0.13.2/seaborn/cm.py);
no Seaborn runtime dependency is introduced. Focused scalar previews retain
up to 4096 characters; original length colors are prepared before truncation.
Nested supporting values stay lazy summaries until their full-value command;
complete nested values retain the existing line virtualization. Detailed
pixel/token/signal tools remain explicit and operate on one column at a time,
while all selected columns and their media previews remain available together.
