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
- [x] Nested import/Inspect: late nested fields and empty/null containers survive
  batch boundaries; malformed JSON remains rejected; full selected values and
  stable source-row identity survive sorting and restoration.
- [x] List profiles: numeric and categorical element statistics across rows,
  nested dimensions/shapes and length summaries; empty/null/object-list cases
  remain inspectable with clear semantics. Preparation runs in workers.
- [x] Final acceptance: full pytest suite, Pyrefly, Ruff, native GUI checks and
  source-preserving saved-session round trips.

Existing v1 and Phase 9–14 acceptance and unfinished UX gates keep their status.

## Step 1 evidence — `e3bb975`

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

## Step 2 evidence — `bd0dd22`

JSON/JSONL record columns and selected JSON/TOML object-browser record views now
retain typed Struct/List values. Polars aligns late struct fields as null, just
as it aligns late top-level fields. Explicit read-as-text serializes complete
containers. Null and empty containers remain distinct; incompatible structures
retain the existing import failure/read-as-text recovery path. Object previews
use `{ ... }`; list previews show their top-level length without decoding their
payloads to Python. Supporting Inspect fields stay compact; choosing a nested
primary field prepares complete indented JSON and virtual scrollable lines.

Focused import/object-view/record/presentation checks: **72 passed**. Pyrefly,
Ruff lint/format and diff whitespace pass. The dedicated Linux Mesa GUI smoke
`uv run python scripts/nested_inspect_smoke.py` renders both object and list
primaries, verifies a complete >4,096-character object, sorts source IDs to
`[1, 0]`, saves and restores the list primary in a fresh process, and preserves
the source. [Report](evidence/nested-columns/inspect.json) and
[screenshot](evidence/nested-columns/list.png). This rendering smoke sets view
state explicitly; it does not claim mouse-input coverage.

## Step 3 and final acceptance

List columns have a distinct physical interpretation, remain independent of
numeric table/ML row features, and can be selected in Profiles. Numeric leaves
use existing exact numeric statistics plus histogram/KDE/ECDF/box/violin views;
string/boolean leaves use category counts. Nested objects retain quality counts
and complete Inspect values. Lists of objects retain container statistics and
Inspect without inventing a scalar distribution.

Null and empty containers contribute no leaf elements; explicit null leaves
remain in element quality counts. Per-depth length means/medians exclude null
containers and include empty containers. Nested shapes report rectangular,
ragged and unknown cases; empty higher-dimensional lists retain `?` for unknown
inner extents. Shape frequencies show at most 12 exact common shapes plus an
Other record count. Category charts/modes retain the existing first-100,000
bound, now measured in flattened elements. Curves retain the existing 2,000
finite-value sample limit. Source-row order makes seeded numeric-list curves
stable across table sorting. Choosing a list is exclusive, like selecting a
category/date; the source table and its row identity remain intact.

Focused list/profile/roles/distribution/nested-import checks: **41 passed**;
profiling boundary regressions plus list checks: **23 passed**. The former
unsupported-list regression now asserts numeric leaf statistics and still checks
unsupported binary columns. Numeric and categorical statistics table layouts
use separate IDs so switching kinds preserves readable column order.

`LIBGL_ALWAYS_SOFTWARE=1 uv run python scripts/list_profiles_smoke.py` renders
all three profile tables, category leaf counts and all five numeric chart modes,
then restores the selected numeric list in a separate process with no text/ML
commands. [Report](evidence/nested-columns/profiles.json) and
[screenshot](evidence/nested-columns/profiles.png). View state is set explicitly;
the mouse-selector automation limitation described above remains unverified.

`uv run python scripts/benchmark_list_profiles.py` measures **100,000 rows**
and **600,000 Float64 leaves**, each row shaped **2 × 3**. Exact profile plus
bounded plotting preparation takes **0.146 s**, metadata-only preview preparation
**5.49 ms**, source table **6.87 MiB**, and whole-process peak RSS **289.4 MiB**.
[Resource report](evidence/nested-columns/list-resources.json). This is a narrow
constant-value fixture, not a capacity guarantee. Source values/IDs are checked
unchanged; no full list payload is decoded into Python for preview.

Final `uv run pytest`: **1,042 passed**, 3 existing PyTorch dependency warnings,
**26.49 s**. `uv run pyrefly check`, `uv run ruff check .`,
`uv run ruff format --check .` and diff whitespace pass. All requested delivery
gates are complete with Linux Mesa rendering/restoration evidence. Arbitrary
heterogeneous field/element types still use explicit read-as-text recovery;
struct schemas align missing keys as null. Additional platforms, accelerated
rendering and the stalled mouse-selector automation are not claimed verified.
