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
Expanded options can make the import panel scroll; status content remains
accessible using its scrollbar. Options start collapsed in ordinary sessions.
Accelerated rendering remains unverified.

M2.1 passed before XML implementation. The final checks below also verify
M2.1 against the completed Phase 2 code.

## M2.2 Tabular XML and nested-input handling

XML extraction accepts UTF-8 records at a configurable relative child path,
a leading descendant search, or the root record itself. Named/wildcard path
segments, namespace aliases, and `{URI}` qualified names are supported;
XPath predicates are rejected with supported-path guidance. Record/field
attributes become `@name` / `field/@name` columns; explicit exclusion is counted
and reported. Namespace-qualified names remain distinct. Missing/empty fields
become null; trimming, null tokens, text mode, scalar inference, and ISO date
parsing are configurable in the GUI. Types use all selected rows, and rows
retain document order and independent UInt64 source IDs.

Nested/repeated fields, mixed content, malformed XML, unmatched/invalid paths,
unknown namespace aliases, DTD/entity declarations, incompatible encodings,
and numeric overflow fail with extraction/record/field guidance. Nested JSON
is rejected for every record, including fields beyond initial batches. Source
files and the active dataset are preserved when imports fail.

Correctness tests cover attributes on records and fields, missing/empty rows,
late fields/type changes across batch/block boundaries, namespace URIs with
slashes, distinct namespaces, descendant/child/wildcard/root paths, date/text/
null/whitespace options, deterministic repeated extraction, unsupported nesting,
malformed input, and metadata changes. JSON array grammar is checked across
small buffer boundaries, including Unicode, escapes, trailing commas, missing
separators, truncation, and extra data. XML comment/CDATA/PI literals and
declaration scanning across UTF-8 buffer boundaries are covered. Preview extraction treats column names
literally; caret/dollar names cannot select different columns in any format.
Parquet timestamp/time/duration previews retain nanosecond precision and nulls.
All six formats have active-state failure preservation tests. Cross-format fixtures prove schema/value equivalence.

The GUI namespace/extraction fixture uses `./s:records/s:record` with
`s=urn:smoke`. Its two prepared rows match the other format fixtures; a nested
XML request fails while the prior table stays visible. Both collapsed status
and expanded extraction controls were visually inspected:
[diagnostics](evidence/format-xml.png),
[settings](evidence/format-xml-options.png). The normal installed CLI and empty
workbench each rendered 30 frames and exited cleanly.

## Parser memory and live responsiveness

The first measurements exposed excess JSON/XML parser memory. The retained
[initial report](evidence/format-benchmark-initial.json) corresponds to
`f7fbf34`: 1m-row JSON/JSONL used 1,404/1,616 MiB, and XML used 3,690 MiB.
These failed the existing fixture memory budget and are not passing evidence.

Validated JSON values now stream through the standard decoder; XML uses
incremental record extraction without retaining the full source tree. Both
convert bounded groups of scalar records into Polars. Batches cap rows and
cells, periodically yield the GIL for rendering, and consolidate bounded groups
once to avoid excessive tiny-column metadata. All fields/types remain present
across batches, including preceding empty rows and late fields. Polars remains
the authoritative in-memory table. This is bounded parser preparation, not
larger-than-memory dataset execution.

```sh
POLARS_MAX_THREADS=8 uv run scripts/benchmark_formats.py \
  --output /tmp/datelier-formats-benchmark-final.json
POLARS_MAX_THREADS=8 LIBGL_ALWAYS_SOFTWARE=1 uv run scripts/format_loading_smoke.py \
  --format JSON --output /tmp/datelier-json-large.ppm
POLARS_MAX_THREADS=8 LIBGL_ALWAYS_SOFTWARE=1 uv run scripts/format_loading_smoke.py \
  --format JSON --rows 100000 --numeric-columns 64 \
  --output /tmp/datelier-json-wide.ppm
# Repeat GUI commands for TSV, JSONL, Parquet, and XML.
```

The [final headless report](evidence/format-benchmark.json) has 20 fresh-process
measurements: 10k/100k/1m × 8 and 100k × 66 for each new format. Each validates
complete table values, source IDs, null counts, bounded first/last pages, and
unchanged source metadata. Each asserts ≤1 GiB peak RSS, ≤250 ms summaries,
and ≤50 ms page preparation. All pass: maxima 770.84 MiB, 1.23 ms, and 0.42 ms.

| Format | 1m × 8 to prepared ms | Peak MiB | 100k × 66 to prepared ms | Peak MiB |
| --- | ---: | ---: | ---: | ---: |
| TSV | 71.55 | 477.62 | 67.39 | 430.64 |
| JSON | 7960.18 | 729.89 | 5776.50 | 622.23 |
| JSONL | 9520.74 | 312.16 | 5883.43 | 500.16 |
| Parquet | 10.32 | 389.07 | 20.59 | 275.46 |
| XML | 12252.12 | 516.77 | 8624.33 | 770.84 |

One run per format/shape is reported, not a repeated-run average. Fixtures,
hardware, versions, source sizes, width/types, wall time, and peak RSS are in the
report. The environment remains Intel i7-13620H / 16 logical CPUs / 31.0 GiB
RAM, Linux 7.0.0-34, CPython 3.14.7, Polars 1.44.2, ImGui Bundle 1.92.900,
NumPy 2.5.3, and eight Polars threads. Fixtures contain six (wide: 64) Float64
features, a String category, and a null every 17 rows in the last feature.
User `row_id` infers as Int64 in text formats; the independent IDs remain UInt64.
Temporary sources are written immediately before reading, so these are cached
local parsing measurements. Peak RSS includes the generated expected table,
import, preparation, and validation.

Live GUI checks start a real load at frame 30 after an idle window appears.
They keep rendering until loading and last-row page preparation finish, then
render another 60 frames. Every run verifies schema/null counts, row identity
near the last row, docked panels, source preservation, and at most 29 rendered
rows per frame. Wide runs select columns 49–64 of 66. The script asserts ≤33 ms
loading-frame p95 and ≤1 GiB peak process RSS; all ten runs pass.

| Format / shape | Load to last prepared display ms | Loading frame p95 ms | Peak MiB |
| --- | ---: | ---: | ---: |
| TSV / 1m × 8 | 109.59 | 11.94 | 679.66 |
| TSV / 100k × 66 | 106.67 | 13.09 | 635.49 |
| JSON / 1m × 8 | 14538.73 | 9.46 | 900.30 |
| JSON / 100k × 66 | 10792.88 | 9.64 | 827.52 |
| JSONL / 1m × 8 | 17791.58 | 10.44 | 514.11 |
| JSONL / 100k × 66 | 11123.79 | 10.12 | 701.87 |
| Parquet / 1m × 8 | 62.71 | 13.91 | 587.34 |
| Parquet / 100k × 66 | 75.67 | 9.38 | 482.55 |
| XML / 1m × 8 | 23112.65 | 11.18 | 724.16 |
| XML / 100k × 66 | 16638.83 | 10.40 | 972.89 |

Reports/screenshots are retained as
`docs/evidence/format-{tsv,json,jsonl,parquet,xml}-{large,wide}.{json,png}`.
Screenshots were inspected for prepared rows, correct column windows, schema,
status, and readable panels. Fast native imports produce only 1–7 loading-frame
samples, so their p95 is descriptive of these short checks, not a general
latency distribution. Measurements detect prepared display on a subsequent
callback and do not claim hardware input latency.

Text validation is slower while sharing the interpreter with the GUI: the
1m JSON/JSONL/XML live runs took about 14–23 seconds. Rendering stayed within
budget. The Phase 0 ≤1/2 second loading budgets are specifically for CSV and
are not claimed for JSON/XML. Memory/page/summary/frame budgets apply here and
pass. These synthetic fixtures do not guarantee capacity for every width/type
mix. Accelerated rendering remains unverified.

## Final phase checks

```text
uv run pyrefly check          0 errors
uv run pytest                151 passed in 9.65s
uv run ruff check .          passed
uv run ruff format --check .  50 files formatted
uv lock --check --offline    passed; 24 packages
git diff --check             passed
```

The full suite uses the M2.1 thread/cache settings. A stricter Pyrefly run with
`--min-severity warn` also returned zero diagnostics. Final small-format GUI
checks rendered 90 frames each for CSV, TSV, JSON, JSONL, Parquet, and XML;
XML also passed a separate expanded-options run. Every failure test retained
the valid prior preview. The installed TSV CLI and empty workbench each
rendered 30 frames. The full benchmark and ten large/wide GUI runs were recorded at `e54c431`;
the final temporal formatting fix (`7a811b6`) also passed the Parquet GUI check
and full suite. All required M2.1 and M2.2 gates pass; Phase 2 is complete.
Phase 3 reversible transformations is next.

## Completed step commits

| Commit | Verified step |
| --- | --- |
| `5e566c6` | Shared import contract, TSV, generic CLI and format controls |
| `a012e2c` | Validated JSON/JSONL, shared source guard, nested diagnostics |
| `4bc824b` | Parquet stored types, explicit columns, nested rejection |
| `919dea3` | M2.1 cross-format acceptance tests and evidence |
| `81d8a0d` | Configurable XML extraction, types, namespace/attribute controls |
| `f7fbf34` | Strict UTF-8 headers and all-format state/source guard tests |
| `4ee9023` | Streaming/batched JSON/XML and benchmark fixtures |
| `589f5bb` | Responsive cell-bounded loading and bounded chunk consolidation |
| `130c320` | Format-neutral empty workbench guidance |
| `1eb6737` | Preserve literal XML declaration text in comments/CDATA/PIs |
| `e54c431` | Literal column access with five-format preview regressions |
| `7a811b6` | Preserve temporal precision in bounded Parquet previews |
