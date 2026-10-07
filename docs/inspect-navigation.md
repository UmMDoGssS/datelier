# Inspect within Explore

Inspect is a tab inside **Explore**, alongside **Profiles**, **Relationships** and
**Correlations**. The separate Inspect dockable panel is removed. Opening a media
collection selects Explore → Inspect. Record settings, linked selection and
prepared results remain owned by each file or record view. Inspect is available
while the exploration dashboard is still preparing.

The selected Explore tab persists through the existing workspace view recipe.
Layouts containing an obsolete Inspect panel entry still reopen Explore. Gallery,
focused record, supporting fields and text-token controls retain their behavior.

## Verification

- `scripts/inspect_navigation_smoke.py` clicks all four tabs using native mouse
  input, confirms they occupy the same row, switches from Gallery to detail and
  advances to source row 1. Saving passes in **170 frames**; an independent process
  reopens in **14 frames**, retaining Inspect and the focused record. The saved
  layout includes an obsolete Inspect window entry. Source bytes remain unchanged.
  [Native report](evidence/inspect-navigation/native.json),
  [selected Inspect](evidence/inspect-navigation/inspect.png) and
  [reopened Inspect](evidence/inspect-navigation/inspect-restored.png) record the run.
- `scripts/inspect_smoke.py` passes in **93 frames**, including all 42 supporting
  fields, Gallery/detail navigation, sort/sample alignment and cross-file selection.
- `scripts/direct_sources_smoke.py` passes in **33 frames**, including native folder
  opening into Inspect and a separate text-line collection with no implicit ML.
- `scripts/text_inspect_smoke.py` passes in **97 save / 31 reopen frames** with
  original Unicode spans, long-text paging and sort/supporting-field alignment.
- `scripts/phase10_workspace_smoke.py` passes in **21 save / 6 restore / 8 recovery
  frames**, retaining the Inspect recipe and dock with usable peer files while a
  missing media member needs recovery.
- **54 focused tests** and the **739-test full suite** pass. The suite reports three
  existing upstream checkpoint warnings. Pyrefly reports zero errors; Ruff lint
  and formatting pass. The two-file workspace test retains independent Inspect
  and Profiles choices, and no text preparation starts during restoration.

Native rendering was verified on Linux with Mesa software OpenGL. Phase 13 and
later feature gates remain open.
