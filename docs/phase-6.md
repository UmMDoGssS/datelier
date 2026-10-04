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
Selections and fitted results are session-only. Layout/theme persistence is M6.2.
