# Phase 1 evidence

Recorded on 2026-10-04 on the Linux/Python 3.14.7 reference environment from
[Phase 0](phase-0.md). Commands use `UV_CACHE_DIR=/tmp/datelier-uv-cache`.

## M1.1 CSV import and dataset state

The headless dataset contract keeps UInt64 source-row IDs separate from user
columns. Reordering/filtering requires aligned IDs, validates uniqueness/range,
and publishes a distinct revision of the same dataset. Public Polars access
uses shallow clones to protect stored revisions without copying column buffers.
Independent imports receive independent dataset identities.

CSV import uses Polars with explicit delimiter, header, quote, null-token,
inference, date, and skipped-record options. UTF-8 is strict. Empty files fail;
header-only files retain a zero-row schema and display a diagnostic. Missing
trailing fields become null; extra fields and invalid quoting/UTF-8 fail.
Mixed columns infer as strings within the inference window; later conflicts
fail with advice to infer all rows or load text. Duplicate headers use Polars'
deterministic suffixes. Source metadata is checked before/after reading;
detected changes prevent publication. Metadata checks do not detect changes
that preserve size, modification time, and inode.

Tests include ordinary numeric/string values, user `row_id` collisions, quoted
delimiters/multiline values, Unicode, custom options, missing/null fields,
mixed inference, header-only/duplicate headers, malformed/empty/missing input,
external source changes, source-byte preservation, revision isolation, and
invalid row identity. The filename contains glob metacharacters to verify
literal file access.

```text
uv run pyrefly check          0 errors
uv run pytest tests/test_import_csv.py tests/test_dataset.py
                             22 passed
uv run pytest                39 passed in 9.32s
uv run ruff check .          passed
uv run ruff format --check .  21 files formatted
git diff --check             passed
```

The full suite used `OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1` and
`NUMBA_CACHE_DIR=/tmp/datelier-numba-cache`. After the two final lint fixes,
Pyrefly, all 22 focused tests, lint, format, and whitespace checks passed again.
M1.1 passes. M1.2 remains open until the background/GUI/performance gates pass.
