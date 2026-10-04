# Phase 6 verification evidence

## M6.1 — Referenced-source workspace persistence

Version-one JSON workspace files store relative source references, size/mtime
and SHA-256, exact format/import options, full operation history and cursor
(including redo), four algorithm settings, semantic plot column names and
exploration/table views. They contain neither table snapshots nor fitted ML
artifacts. The strict allowlisted recipe codec rejects unknown fields/types,
invalid enums/shapes, duplicate JSON keys, unsupported versions, nonstandard
JSON numbers and oversized files. Supported nonfinite operation scalars use
explicit tagged JSON. Saves use a flushed temporary file and atomic replacement;
source paths, symlink aliases and hardlinks are protected.

Restore checks source content, imports with the saved options, validates all
history including redo, and prepares a preview before publishing. Save,
fingerprinting, import and replay run in workers. New requests abandon older
results; revision changes reject obsolete publication. Failed imports/replays
retain the active dataset/history/settings. Missing/unreadable sources show
relink controls. Changed content requires an explicit checkbox before replay;
identical moved content can relink without accepting a change. Relative sources
can move with their workspace. Changed/missing plot columns reset to available
views; analysis inputs retain available numeric columns. Loading settings never
runs ML. Saved analysis recipes share the workbench's common inputs, preprocessing,
seed and dimensions, with separate algorithm parameters/sample limits.

Verified on 2026-10-04, Linux/Python 3.14.7 and Mesa software OpenGL:

- Recipe foundation: **25 focused tests**, Pyrefly zero errors and Ruff checks.
  Commit `3e5464c`.
- Background restore/relink: **34 focused tests**, including same-size/same-time
  content mutation, mutation during import, failed redo, changed/moved/missing
  files and obsolete/newer jobs; Pyrefly/Ruff pass. Commit `7d9d494`.
- GUI integration: full suite **312 passed in 12.23s**, Pyrefly zero errors,
  Ruff lint/format and diff checks passed.
- `scripts/workspace_smoke.py` passed **31 save frames / 44 reopen frames**:
  saved nondefault plot/analysis settings, an undo cursor and redo recipe;
  rendered a failed-open status while retaining active data; restarted the GUI,
  rendered a missing-source diagnosis, relinked the moved source, restored the
  settings/views, redid the sort and selected the correct linked source row.
  Zero implicit ML jobs/results; source bytes unchanged.
- [Reopen screenshot](evidence/workspace-reopen.png) was visually inspected:
  workspace controls/status, sorted table/identity, selected row, categorical
  scatter colors and saved analysis seed/whitening rendered correctly.

Commands use `UV_CACHE_DIR=/tmp/datelier-uv-cache uv run --offline` because the
sandbox cannot write the default uv cache. Required GUI commands run outside
that sandbox to access the desktop display:

```sh
POLARS_MAX_THREADS=8 uv run pytest
uv run pyrefly check
uv run ruff check .
uv run ruff format --check .
LIBGL_ALWAYS_SOFTWARE=1 POLARS_MAX_THREADS=8 uv run scripts/workspace_smoke.py
```

The live gate drives controls through frame hooks; physical button clicks are
not claimed. Accelerated rendering and other platforms remain unverified.
Recipe files cap at 2 MiB and 1,000 operations. Fingerprinting reads the source
in bounded chunks; a save rejects size/mtime changes since import. This does
not track byte changes made before the first fingerprint with deliberately
preserved size/mtime. Restores always compare the recorded content digest.
Selections and fitted results are session-only. M6.2 evidence follows.

## M6.2 — Saved layouts, themes and plot preferences

Version-one user preferences save dock/window/table settings, panel visibility,
Dark/Light/Classic theme, bounded plot settings and exploration/table views.
The default file is `$XDG_CONFIG_HOME/datelier/preferences.json` (falling back to
`~/.config/datelier/preferences.json`). Preferences load before the first GUI
frame. A saved docking policy is configured before runner initialization and
ImGui settings load at post-init; this prevents Hello ImGui's default builder
from replacing a restored arrangement. Default splits live in a separate,
resettable layout module.

The **Preferences** menu changes theme, saves preferences, restores the last
saved layout, resets layout/panel visibility, or resets plot defaults. The
existing **View** menu can reopen closed panels. Preferences also save on normal
exit; the bounded snapshot is taken while the graphics context exists and the
atomic write runs in a worker. Shutdown waits for requested preference writes;
write failures appear in the menu or on stderr at shutdown. Smoke runs avoid
personal preference files unless a temporary path is explicitly supplied.

Global plot defaults restore available columns by name on dataset import.
Workspace plots/views override those defaults on workspace restore. Missing
optional settings use defaults. Unsupported overall preference versions reset
with a message; outdated/unusable layouts and invalid theme/plot/view sections
recover independently, retaining other valid sections. Layout snapshots cap at
256 KiB; preference files cap at 2 MiB. Resetting a layout changes no dataset,
operation history or revision. Selection highlights remain functional afterward.
Selections, ML artifacts, plot zoom/pan and 3D camera position are session-only.

Final verification on 2026-10-04:

- Full suite: **333 passed in 12.15s**, including 15 preference recovery/source
  protection tests, six exact-option import → workspace → replay round trips
  (CSV/TSV/JSON/JSONL/Parquet/XML), and all preceding phase regressions.
- Batch Pyrefly: zero errors. Ruff lint/format and diff whitespace checks passed.
- `scripts/preferences_smoke.py` runs **three fresh GUI processes**: 21 frames to
  save a rearranged table/hidden Analysis/Light theme/nondefault plots; 15 frames
  to import with global defaults; 67 frames to restore a workspace and verify
  precedence, reset layout, restore the saved arrangement again, reset again,
  switch to Classic and verify linked table/plot selection. The source, recipe
  and dataset revision remain intact; no implicit ML runs.
- The workspace/relink live smoke also passed with preferences integration
  (**31 save / 45 reopen frames**).
- Existing `scripts/selection_smoke.py`: **168 frames**, sort/filter/sample
  identity, both selection directions, wheel zoom, middle pan and Shift brush
  passed with source preservation. This uses Dear ImGui mouse/key events and
  backend cursor positioning.
- [Live report](evidence/preferences-live.json),
  [restored Light layout](evidence/preferences-light.png), and
  [Classic/reset/selection screenshot](evidence/preferences-reset.png).
  Both screenshots were visually inspected: the rearranged table remains in
  the left lower dock with Analysis hidden; reset restores all default panels
  with matching selected table/plot identity.

Reproduction:

```sh
LIBGL_ALWAYS_SOFTWARE=1 POLARS_MAX_THREADS=8 uv run scripts/preferences_smoke.py
LIBGL_ALWAYS_SOFTWARE=1 POLARS_MAX_THREADS=8 uv run scripts/workspace_smoke.py
LIBGL_ALWAYS_SOFTWARE=1 POLARS_MAX_THREADS=8 uv run scripts/selection_smoke.py
POLARS_MAX_THREADS=8 uv run pytest
uv run pyrefly check
uv run ruff check .
uv run ruff format --check .
```

Preference/theme/layout actions use frame hooks; physical menu clicks are not
claimed. The existing gesture smoke uses injected ImGui/backend input. Linux
with Mesa software OpenGL remains the verified platform/renderer. Accelerated
rendering and other platforms remain unverified. M6.1, M6.2 and Phase 6 pass;
Phase 7 end-to-end hardening and release readiness are the next gates.
