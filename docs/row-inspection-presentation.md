# Row inspection presentation — authorized 2026-10-13

The requested follow-up makes Inspect a detailed row browser for all types,
with all columns shown by default and a retained column selector. Gallery rows
use separate name/value tables; focused records use ruled column titles and
highlighted values. Preview and Inspect share value colors. Profiles use one
row per column and one column per statistic, with deterministic separated plot
hues for the displayed series.

## Verified steps

- [x] Preview colors: opaque white null cells with bold black text, including
  selected rows; original Unicode string lengths use interpolated Crest with
  the existing percentile/linear/custom scale controls. Categories keep their
  categorical palette when their values are not strings. String/Categorical/Enum
  text uses length shading even when repeated values infer a categorical role.
  Shading remains a display-only setting.
- [x] Inspect: all selected columns, shared styling, separated gallery tables,
  ruled focused fields, lazy media previews and retained detailed tools.
- [x] Profiles: wide statistics tables and separated saturated comparison hues.
- [x] Full-suite and native acceptance.

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

Step 3 checks: 29 focused profile/statistics/list/distribution tests, Pyrefly,
Ruff lint/format and diff whitespace pass. Numeric statistics have one row per
column and preserve original values, null/nonfinite quality and exact integer
extrema above 2**53. Worker-prepared list structure/length/shape tables remain
separate from leaf statistics. Summary tables freeze the Column header during
horizontal scrolling; mean/std/min/max/median lead the numeric columns.

For the displayed set, sorted unique series identities are assigned evenly
spaced HSV hues with a deterministic hash rotation, saturation 0.78 and value
0.95. Reordering or restoring the same set preserves colors across histogram,
KDE, ECDF, box and violin views. Changing the selected set may reassign colors;
the minimum circular hue gap is 1/N, so large sets necessarily have closer hues.
Explicit comparison color overrides remain intact. The same set-based palette
also separates overlaid image-profile histogram channels.

Native Dark/Light checks pass all five plot modes and the 3-row/18-column table
(51 frames each); the existing profile sizing/navigation/selector workflow
also passes. `scripts/rebuild_profile_presentation_smoke.py` writes reproducible
screenshots/reports under `/tmp/datelier-profile-presentation`. No source edits,
implicit ML, tokenizer training or playback are introduced.

The final string coverage refinement passes 16 focused table/record tests,
Pyrefly, Ruff and native table/focused-row checks. String-valued identifiers,
references and categorical/Enum text share the length scale; nontext categories
retain stable category colors. A new native restore assertion verifies the
chosen shown-column order. Selected-row null checks pass in Dark and Light.

## Final acceptance — 2026-10-13

`uv run pytest -q`: **1205 passed**, 3 existing PyTorch warnings, 35.48 s.
Full Pyrefly: zero errors (the existing one suppression remains). Full Ruff
lint/format and `git diff --check` pass. No dependency/lockfile changes.

Native Mesa checks cover Dark/Light selected null cells, gallery/focused rows,
both image previews, all five numeric plot modes and actual statistics rows,
original pixel/text-span/waveform tools, sorted array-gallery opening, and the
existing profile sizing/navigation/selector workflow. Fresh-process table
restoration retains custom ranges, badges, reference mappings, linked source
selection and the chosen shown-column order. Final save/restore runs take
178/31 frames, with p95 frame intervals 14.95/14.01 ms; the shared preview cache
peaks at 9216 GPU bytes and at most three uploads in one frame. Sources are
preserved, and restoration starts no ML, tokenizer training or playback.

The implementation is delivered in verified commits `63c1d7a`, `89ffdf4`,
`89ab54c`, and `5fe90df`. The earlier Viridis commit is superseded by the Crest
update. Full-resolution media/token/signal tools still select one column;
row fields and their previews are shown together. All existing Linux rendering,
human listening and unfinished Titanic usability assumptions retain their status.
