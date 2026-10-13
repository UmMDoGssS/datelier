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
- [ ] Full-suite and saved-layout acceptance.

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
