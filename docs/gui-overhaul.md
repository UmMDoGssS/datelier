# GUI architecture and workflow overhaul

Authorized on 2026-10-10 after code exploration and user decisions. Production
GUI baseline: 122 Python modules, 15,543 lines, 62 classes and 110 module-level
functions, with no shared component inheritance. This is an architecture and
workflow change, not a data-engine rewrite. Existing capability evidence remains
valid; the outstanding Titanic usability gates and deferred audio listening
check retain their status.

## Decisions and acceptance contract

Use classes for views and reusable widgets, with abstract component families and
immediate-child rendering. Pure formatting, drawing and geometry helpers may
remain functions. Constructor injection supplies narrow prepared state and
commands; leaf components must not receive whole file/editor sessions.
Application controllers coordinate jobs, selections, navigation and persistence.
Keep source/view/revision identity, shared workers, lazy media loading and GUI
thread texture ownership. Background completion must not steal navigation focus.

The final shell has four dockable panels: source/columns, canvas, context and
table. Central tabs are Profiles, Relationships, Correlations, Inspect and Compare
files; comparison subtabs are Columns, Text, Images and Audio. Context holds View,
Transform and History. Remove standalone Analysis after relocating every unique
setting/result, including cluster centers/inertia and provenance. Export becomes
a File-menu dialog. Switching file tabs returns to that file's last inspection
view and preserves comparison drafts. All modalities have equal acceptance
weight. Keep existing themes, Unicode fonts and dependencies.

Column pickers share search, role groups, virtualization and bulk actions, but
retain independent selections, ordering and domain eligibility/limits. Viewport
components share resize/Auto/Expand/Restore while preserving content-specific
zoom, axes/cameras, selection, pixel readouts and token spans. Keep gallery cards
bounded. Move gesture help out of normal content; retain data facts, errors,
sampling, exclusions and truncation. Recipes/settings survive migration; old
docking/hidden-panel state resets with a notice. Planned formats: session v3,
preferences v2, layout v2, with legacy single-source/v2 session readers.

## Bounded delivery and gates

| Step | Delivery | Status |
| --- | --- | --- |
| 1 | Baseline, component contracts, stable probe and an existing panel pilot | Complete |
| 2 | Application/file runtime controllers and explicit lifetimes | Pending |
| 3 | Reusable column selectors and content viewports | Pending |
| 4 | Polymorphic tabular exploration and complete contextual analysis | Pending |
| 5 | Structured and multimodal browsers/record components | Pending |
| 6 | Shared comparison hierarchy with specialized content | Pending |
| 7 | Redesigned shell, focus behavior and persistence migration | Pending |
| 8 | Remove transitional wiring and complete integrated acceptance | Pending |

Each step requires Pyrefly, focused behavioral tests, Ruff lint/format checks,
applicable native GUI smoke checks, diff review and its own commit before the
next begins. The final milestone also requires the full suite, fresh-process
restoration, screenshots/input checks at 1024×768, 1280×800 and 1600×1000 across
all themes, and established modality resource gates. Unperformed gates stay open.

## Baseline evidence

Before implementation, 38 targeted editor/session/schema-role/profile-selection/
axis tests passed. The existing two-file benchmark passed 30 open/close cycles
with 100,000 rows and eight numeric columns per file: 12.48 ms frame p95,
494.69 MiB peak RSS, 189.13 ms maximum cycle preview and 0.33 ms maximum close.
Four workers, zero outstanding jobs/retained closed sessions and unchanged source
bytes pass. [Raw report](evidence/gui-overhaul/baseline-tabs.json) preserves the
original budgets: 33 ms frame p95/close, 2 s preview, 1 GiB peak RSS, 96 MiB
retained growth and at most four workers.

GUI checks require desktop display access: the sandbox cannot connect to :0.
The benchmark was rerun successfully with reviewed desktop access and Linux
Mesa software OpenGL. Use `LIBGL_ALWAYS_SOFTWARE=1 POLARS_MAX_THREADS=8
UV_CACHE_DIR=/tmp/datelier-uv-cache uv run --offline` for native commands.
Representative prior captures remain in the existing modality evidence folders;
fresh redesigned-shell visual/input acceptance has not yet run.

## Step 1 — Component and schema pilot

`Component`, `Container`, `Panel` and `FrameContext` define the first rendering
contract. The schema panel delegates to summary/table components, and the table
renders visible row components. `SchemaController` prepares immutable column
metadata once per revision, receives only an edit-command dependency and rejects
stale, unavailable, busy or failed role changes. Native rendering no longer reads
the dataset or prepares role metadata.

`GuiProbe` records targets by file/view/revision/component path and releases them
at each frame boundary. `run_gui` gains an additive `on_probe_frame` hook;
existing hooks remain usable during migration. `component_schema_smoke.py` uses
that hook to exercise native role selection and undo without accessing widget
internals. Current panel labels/layout and workspace formats remain unchanged.
Native keyboard navigation is now enabled. The original app enabled docking
only, so popup keyboard selection was unavailable. The preview smoke explicitly
reveals the schema dock tab instead of requiring a hidden tab to have rendered.

Verification on 2026-10-10:

- Batch Pyrefly: zero errors (one existing suppression).
- Schema/probe and existing editor/workspace/role/profile/axis tests: **41 passed**.
- Ruff lint, format and diff whitespace checks pass.
- Native component input: **48 frames**, **13.03 ms p95**; mouse opens the combo,
  keyboard selects Numeric, undo restores the inferred ID role. Source bytes,
  values and source row IDs are preserved; zero implicit ML runs.
- Native 10,000-row/eight-column preview: **180 frames**, **133.64 ms** first
  preview, **32.93 ms p95**, at most six rendered rows. Background reload, schema
  docking, end-of-table row identity and wheel scrolling pass. Pixel capture was
  visually reviewed for schema labels, role controls and bounded table rendering.

[Component input report](evidence/gui-overhaul/schema-component.json),
[preview report](evidence/gui-overhaul/schema-preview.json) and
[preview capture](evidence/gui-overhaul/schema-preview.png) retain the evidence.
Native input is synthetic ImGui input, not human pointer timing. The redesigned
shell, all-family sizing and whole-milestone regressions remain outstanding.

Commands, using the environments above:

```sh
uv run --offline pyrefly check
uv run --offline pytest tests/test_schema_controller.py tests/test_gui_probe.py tests/test_editor_sessions.py tests/test_workspace_gui_state.py tests/test_column_roles.py tests/test_profile_selection.py tests/test_axis_controls.py
uv run --offline ruff check .
uv run --offline ruff format --check .
uv run --offline scripts/component_schema_smoke.py
uv run --offline scripts/inspection_smoke.py --output /tmp/datelier-component-preview.ppm
```
