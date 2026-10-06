# Phase 10 — Interpretations, previews, and Inspect

Phase 9 is the entry baseline. Phase 10 is being delivered in bounded steps:

1. Import interpretations and exact first-source-column identifier rule.
2. Nearby reference index, explicit mappings, prioritized lazy image/text previews.
3. Typed conditional presentation and saved per-view scales.
4. Direct media/text record collections and shared gallery/detail Inspect.
5. Native restoration, source/revision/lifecycle and measured resource acceptance.

M10.2–M10.4 and the overall phase remain open until their recorded checks pass.
The existing Titanic UX acceptance status is unchanged.

## M10.1 interpretation behavior

Lexical evidence from at most 256 non-null strings recognizes image/audio/text
extensions and local path syntax without accessing the filesystem. Prose has
priority over identifiers. At import, a nonempty first source column with fully
unique, non-null integer/string values becomes Identifier when recognizable
reference/text evidence does not win. Floats, empty, duplicate and null-containing
first columns do not satisfy that rule. Named unique IDs elsewhere remain
recognized. Interpretation evidence and physical dtype remain distinct.

Same-type row edits retain imported interpretations, so filtering a category down
to unique values cannot create an identifier. Type changes infer a compatible
role without reapplying the first-source-column import heuristic. Overrides use
the existing replayable operations and undo/redo; profiles, colors and automatic
ML feature controls exclude references/IDs/text unless explicitly reinterpreted.
No source cells or row identities are rewritten and no payload is loaded.

Verification on Python 3.14.7/Linux uses
`UV_CACHE_DIR=/tmp/datelier-uv uv run --no-sync` with the existing locked environment.
Focused interpretation, roles, comparisons, exploration, profiles, scatter,
selection, transforms and workspace controls: **67 passed**. Pyrefly reports
zero errors; Ruff lint/format and diff whitespace pass. The native Mesa Schema
smoke (`LIBGL_ALWAYS_SOFTWARE=1 POLARS_MAX_THREADS=8 ... python
scripts/column_roles_smoke.py`) passes **61 frames**, real override/undo,
identifier feature exclusion, unchanged Titanic bytes and zero implicit ML runs.
The GUI requires access to the local display outside the filesystem sandbox.
Historical numeric-chart fixtures now use explicitly floating first features;
new fixtures directly cover the authorized integer/string ID rule.

M10.1 passes. The milestone full suite reports **568 passed**.

## M10.2 dependency and scheduling foundation

Pillow **12.3.0** is added by `uv add pillow`, with the lockfile updated by uv.
The Linux/Python 3.14 probe decodes a 400×200 RGB PNG in a worker into a contiguous
128×64 RGBA thumbnail; **30 native Mesa frames / six texture uploads** render it
and release owning handles before backend teardown. The installed ImGui Bundle
`TextureGpu` API owns and releases textures on the GUI thread. Pillow's
[image API](https://pillow.readthedocs.io/en/stable/reference/Image.html) documents
lazy open and thumbnail behavior; this probe is Datelier's dependency evidence.

The shared bounded scheduler accepts priority: visible/selected preparation
precedes queued discovery, FIFO within equal priorities; executing work continues
until completion or cooperative abandonment. Cancellation removes queued closures
and releases capacity. Owners still close independently. Nine focused scheduling,
file-session and editor-session tests pass; Pyrefly, Ruff lint/format and whitespace
checks pass. This foundation does not yet pass M10.2's feature/resource gates.
