# Text tables and nested JSON column inspection

Authorized follow-up, 2026-10-10. Deliver in three verified steps:

1. Display exact text corpus statistics and document lengths in scrollable tables.
2. Preserve JSON/JSONL and structured record-view object/list columns, compact
   object previews, and complete nested primary values in Inspect.
3. Profile recursively flattened list elements according to their scalar type;
   show separate list length/shape statistics, with explicit null/empty/ragged
   handling. Preserve source rows, pipeline recipes and workspace restoration.

## Gates

- [x] Text statistics tables: existing exact totals, ratios, entropy and length
  quantiles remain available; native text rendering/restoration passes.
- [ ] Nested import/Inspect: late nested fields and empty/null containers survive
  batch boundaries; malformed JSON remains rejected; full selected values and
  stable source-row identity survive sorting and restoration.
- [ ] List profiles: numeric and categorical element statistics across rows,
  nested dimensions/shapes and length summaries; empty/null/object-list cases
  remain inspectable with clear semantics. Preparation runs in workers.
- [ ] Final acceptance: full pytest suite, Pyrefly, Ruff, native GUI checks and
  source-preserving saved-session round trips.

Existing v1 and Phase 9–14 acceptance and unfinished UX gates keep their status.

## Step 1 evidence

`uv run pyrefly check`, focused text profile/statistics tests (**5 passed**),
`uv run ruff check .`, `uv run ruff format --check .` and diff whitespace pass.
`LIBGL_ALWAYS_SOFTWARE=1 uv run python scripts/text_statistics_smoke.py` renders
both tables and restores the selected field in an independent process without
implicit corpus work; the script explicitly requests the profile. The synthetic
source remains unchanged. [Report](evidence/nested-columns/tables.json) and
[screenshot](evidence/nested-columns/tables.png) record the result.

The existing `text_profile_navigation_smoke.py` mouse-input scenario stalled at
its selector on this display; it did not pass. The dedicated rendering smoke
uses explicit view state and scrolling. Linux Mesa rendering is verified;
this step does not claim additional native selector-input acceptance.
