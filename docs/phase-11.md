# Phase 11 — Structured objects, arrays, and checkpoints

Phase 11 is underway on the verified Phase 10 baseline. Its completion gate
remains open until M11.1–M11.4 and the full restoration/resource acceptance pass.

The bounded delivery sequence is:

1. Typed JSON/TOML sources, preserved object hierarchy and node extraction.
2. Native tree navigation and independently editable named table views with
   whole-session restoration and source/node/record provenance.
3. NPY/NPZ metadata, selected-member temporary storage, mapped slices and plots.
4. Confirmable array record axes/layouts, aligned supporting fields and saved views.
5. Optional CPU PyTorch installation, restricted checkpoint browsing and acceptance.

## Structured source foundation

`ImportFormat.OBJECT` and `ObjectOptions` support explicit JSON object loading
and automatic `.toml` opening. Immutable nodes retain nested arrays/objects,
scalar types and TOML date/time values, with bounded scalar previews. Typed node
paths distinguish string keys from array indices, including punctuation in keys.
Selected arrays of flat scalar objects enter the existing Polars pipeline;
source-row IDs are original record indices within the selected node. TOML
calendar/time fields use lossless ISO text in extracted tables. TOML nonfinite
floats remain nonfinite; invalid JSON constants/overflow, duplicate keys,
malformed sources and unavailable/incompatible nodes fail locally. Empty/scalar
sources remain browsable; empty arrays without a schema cannot be table views.
Mixed scalar types can be read explicitly as text. Legacy flat JSON/JSONL import
behavior remains covered. No source bytes are rewritten.

Node options use the strict workspace recipe codec, and source fingerprint checks
and operation replay apply to extracted tables. This foundation does not yet
provide named view ownership or the native tree; M11.1 remains open.

Verification on Linux/Python 3.14 uses `UV_CACHE_DIR=/tmp/datelier-uv uv run
--no-sync`: focused object/JSON/format/workspace tests **115 passed**; Pyrefly
**zero errors** (one existing suppression); Ruff lint/format (**310 files**) and
diff whitespace pass. Native Mesa smoke: blank workbench **20 frames**, TOML
metadata source **30 frames**. Local display access requires sandbox escalation;
the initial sandboxed GLFW attempt could not open display `:0`, and the authorized
retry passed. Native tree input, named views, full-suite milestone evidence and
all M11.2–M11.4 gates remain outstanding.
