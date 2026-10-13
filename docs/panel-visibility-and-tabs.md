# Panel visibility and file tabs — authorized 2026-10-13

The View menu must expose every closable workbench panel, including Explore and
Source browser, so accidentally hidden panels can be recovered individually.
Remove the redundant Context/Table buttons beside file tabs and put the new-file
`+` button beside the tabs. Preserve active-file selection, reordering, closing,
undo/redo and saved panel visibility.

- [x] View switches for all four panels; restore hidden Explore/source panels
  with native menu input.
- [x] Remove the Context/Table toolbar buttons and move `+` into the file tab
  bar; verify new-file creation and compact Context access through View.
- [x] Full-suite and saved-layout acceptance.

Step 1 passes 28 focused navigation/preferences/workspace/source tests, full
Pyrefly/Ruff checks and native View-menu input in 125 frames. All four switches
are present. Saved hidden Explore and Source browser panels can be reopened
individually; Explore can be hidden and reopened again without resetting the
layout or changing the source. Menu entries use the panel's own label and live
visibility state.

Step 2 passes 41 focused editor/session/navigation/preferences tests, full
Pyrefly/Ruff checks and native tab/docking/compact workflows. The `+` is a tab-bar
button immediately after the file tabs; its order is rebuilt when a new file is
created or the last file is closed. Native input verifies new-file creation,
closing, last-tab replacement, duplicate filename identity, drag reordering and
active-file/comparison draft behavior in 119 frames (about 14.0 ms p95).
Context/Table toolbar buttons are absent. Compact Context access now uses
View → Context; the updated compact workflow passes in 192 frames and native
docking/reset passes in 82 frames. The final compact screenshot is
`/tmp/datelier-panel-tabs-compact.png`.

Final acceptance passes all 1,214 tests (three existing PyTorch warnings), full
Pyrefly with zero errors, and Ruff lint/format checks. Panel recovery passes
again with the completed toolbar. Separate-process saved default layout
restoration passes at wide/compact sizes (25 frames each). Native Sort/Undo/Redo
and source-bound export checks also pass in 252 frames. Sources remain unchanged
and no ML or playback starts implicitly. Linux Mesa rendering is verified;
existing accelerated/platform and unrelated human usability gates retain their
status.

Native checks: `scripts/rebuild_panel_views_smoke.py`,
`scripts/rebuild_tabs_smoke.py`, `scripts/rebuild_docking_smoke.py`,
`scripts/rebuild_gui_smoke.py --width 1024 --height 768`,
`scripts/rebuild_layout_restore_smoke.py`, and
`scripts/rebuild_workflow_smoke.py`, run with `uv run python` and
`LIBGL_ALWAYS_SOFTWARE=1 POLARS_MAX_THREADS=8`.
