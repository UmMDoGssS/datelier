# Phase 2 evidence

Recorded on 2026-10-04 on the Linux/Python 3.14.7 reference environment from
[Phase 0](phase-0.md). Commands use `UV_CACHE_DIR=/tmp/datelier-uv-cache`.
Dependencies and the lockfile are unchanged. GUI checks use Mesa software OpenGL
and require access to the reference X11 display outside the filesystem sandbox.

## M2.1 TSV, JSON/JSONL, and Parquet

The shared import result carries the dataset, concrete options, format, and
human-readable diagnostics. CSV/TSV share strict delimited parsing; format
selection uses a case-insensitive extension or an explicit GUI override.
JSON accepts an array of flat record objects; JSONL/NDJSON accepts one flat
object per nonblank line. Every record is validated, including late fields.
All records inform type inference, missing fields become null, and text mode
retains JSON nulls. Nested objects/arrays, duplicate keys, nonstandard nonfinite
literals, out-of-range numbers, scalar records, and wrapped JSON are rejected
with record/line/field context. No nested fields are silently discarded.
Temporary Python records are used only for validating the JSON boundary;
Polars remains the authoritative table after import.

Parquet preserves stored scalar types (including integer width, date, datetime,
decimal, and binary). Optional column names explicitly select imported fields;
unknown columns fail. Nested columns must be excluded or flattened before
import. Zero-row Parquet retains its schema. Empty/schema-free JSON fails with
an actionable message. All adapters use the read-only source metadata guard
and the existing revision/request-aware background publication contract.
Metadata checks do not detect changes that preserve size, mtime, and inode.

Cross-format fixtures assert equivalent schemas, values, null counts, prepared
pages, and source IDs for CSV, TSV, JSON, JSONL, and Parquet. Additional tests
cover options, malformed data, UTF-8/Unicode, late JSON keys/nesting, duplicate
keys, empty data, stored Parquet types, nested column exclusion, and source
preservation. Existing stale-job, abandonment, and preview tests still pass.

```text
uv run pyrefly check          0 errors
uv run pytest tests/test_import_formats.py
                             10 passed
uv run pytest                92 passed in 9.52s
uv run ruff check .          passed
uv run ruff format --check .  41 files formatted
git diff --check             passed
```

Full tests use `OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1` and
`NUMBA_CACHE_DIR=/tmp/datelier-numba-cache`.

```sh
POLARS_MAX_THREADS=8 LIBGL_ALWAYS_SOFTWARE=1 uv run scripts/format_smoke.py \
  --format TSV --output /tmp/datelier-tsv.ppm
# Repeat with CSV, JSON, JSONL, and Parquet and corresponding output names.
```

Each format rendered 90 frames, verified a prepared two-row preview, aligned
source IDs, schema/null counts, docked panels, and source-byte preservation.
At frame 30 the script requests a malformed file; failure appears while the
previous valid preview stays active. JSON/JSONL specifically assert the nested
field diagnostic. Reports and screenshots are retained under
`docs/evidence/format-{csv,tsv,json,jsonl,parquet}.{json,png}`. Screenshots were
visually inspected for correct previews, schema/null values, and diagnostics.
TSV's expanded options make the import panel scroll; remaining status content
is accessible using its scrollbar. Accelerated rendering remains unverified.

M2.1 passes. M2.2 and the Phase 2 exit remain open.

## Completed step commits

| Commit | Verified step |
| --- | --- |
| `5e566c6` | Shared import contract, TSV, generic CLI and format controls |
| `a012e2c` | Validated JSON/JSONL, shared source guard, nested diagnostics |
| `4bc824b` | Parquet stored types, explicit columns, nested rejection |
