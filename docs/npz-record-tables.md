# Aligned NPZ record tables

The user-authorized follow-up on 2026-10-08 is complete. New NPZ sources whose
members all have the same first-axis length open as record tables. For the
reported `heatmap_record.npz` shapes `(4, 64, 96)`, `(4,)` and `(4,)`, this means
four rows and columns named `heatmaps`, `labels` and `scale`.

## Bounded delivery

1. Prepared aligned-column tables, scalar dtype preservation and lazy array
   references, with mismatch/unsafe/empty correctness tests. Verified and
   committed as `3051c59`.
2. Default opening, per-column image/heatmap Inspect, metadata opt-out,
   saved-option migration and native opening/restoration verification.

## Behavior and integrity

- Every member must have a usable non-scalar header and the same first dimension.
  Mismatches, scalar members or unsupported/corrupt members retain the member
  metadata listing. NPY retains its existing listing. Zero-length aligned arrays
  produce a zero-row table with the original column names and scalar dtypes.
- One-dimensional members become Polars scalar columns in import workers.
  Existing scalar conversion rules retain precision: float16 uses Float32,
  endian numeric values become native equivalents, and unsupported scalar types
  retain readable text with diagnostics. Numeric scalar fields infer Numeric;
  analysis-role overrides remain available and reversible.
- Larger arrays remain descriptive string references in the table. Original
  multidimensional values remain in the source, addressed by member name and
  stable first-axis row ID. Sorting/filtering preserves that identity.
  Numeric per-record matrices infer heatmap Inspect. A single unambiguous channel
  axis of size 1–4 in a three-dimensional record supports image Inspect.
  Generic/ambiguous shapes remain accessible through Source browser and explicit
  record configuration; they are never silently truncated into scalar columns.
- Array descriptions do not enter nearby-file resolution or file-preview jobs,
  and use normal table row height. Multiple array columns select their own
  payload in focused Inspect, image profiling and image-comparison bindings.
  Numeric heatmap collection colors retain their existing explicit-image-layout
  requirement; this follow-up changes record display, not collection statistics.
- Import settings expose **Aligned NPZ members as record columns**. Disabling
  it preserves the full member metadata table and source slicing controls.
  Saved workspaces retain this choice. Recipes written before the new option
  decode as metadata mode, preserving member-row selections and history.
- Aligned workspaces reconstruct scalar columns and operations in workers.
  They do not decode array grids, launch whole-collection profiling, run ML,
  train tokenizers or play audio during restoration. Explicit named record
  mappings retain their original deferred preparation workflow.
- Source files are read only. Import stores release their temporary members;
  payload inspection continues through the existing bounded shared array store.

## Verification

`uv run pytest` passes **1,024 tests** (three existing PyTorch warnings), including
eight aligned-NPZ tests and the prior array/mixed-session regression coverage.
`uv run pyrefly check` reports zero errors. `uv run ruff check .`,
`uv run ruff format --check .` and `git diff --check` pass. The sandbox's default
UV cache was read only, so checks used `UV_CACHE_DIR=/tmp/datelier-uv-cache` and
`uv run --offline` against the existing locked environment.

The preparation test verifies the sample shapes, four rows, member column names,
Int32/Float32 scalars, Numeric/Image roles, unchanged source bytes and exactly
two scalar-member extractions without reading heatmap grids. Additional tests
cover unequal lengths, scalar/object members, empty arrays, a member named
`record_index`, endian scalars, strings, NPY fallback, metadata opt-out, old/new
option round trips and two independent image locators after sorting.

Native checks use `scripts/npz_records_smoke.py` with Linux Mesa software OpenGL:

```sh
LIBGL_ALWAYS_SOFTWARE=1 POLARS_MAX_THREADS=8 OMP_NUM_THREADS=1 \
UV_CACHE_DIR=/tmp/datelier-uv-cache uv run --offline python \
scripts/npz_records_smoke.py --output docs/evidence/npz-records
```

Separate `--restore`, `--view table` and `--view heatmap` processes verify
fresh-process restoration and capture each layout. The synthetic counterpart
adds an RGB member to the reported three-column sample to verify changing the
primary array column. Reports and reviewed screenshots:

- [Record table](evidence/npz-records/table.png).
- [Heatmap Inspect](evidence/npz-records/heatmap.png) and
  [heatmap report](evidence/npz-records/heatmap.json).
- [Image Inspect](evidence/npz-records/image.png) and
  [complete opening report](evidence/npz-records/full.json).
- [Restored image Inspect](evidence/npz-records/restored.png) and
  [fresh-process report](evidence/npz-records/restore.json).

The complete opening run verifies initial grid extraction count zero, sorted
source IDs `[3, 1, 2, 0]`, heatmap source record 3/pixel 18,432, RGB source record
3/pixel `(40, 5, 9)`, separate member locators and source hash preservation.
The restore run retains the scalar table, sorting, row selection, primary member
and Profiles tab before explicitly navigating to Inspect. No grid preparation
is active before that navigation. These small fixtures establish this follow-up's
correctness and native smoke coverage; they do not establish a new capacity
guarantee or additional platform/rendering support.
