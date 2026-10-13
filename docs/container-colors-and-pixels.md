# Container colors and pixel rendering — authorized 2026-10-13

The row presentation refinement makes identifier values neutral, removes
conditional backgrounds from image/heatmap fields in Inspect, and colors
generic arrays/lists by the mean of their elements. Array-backed images and
heatmaps also use element means in Table, where they remain metadata cells.
Images must retain sharp original pixels when enlarged.

- [x] Role/view rules: identifiers stay neutral; Inspect image/heatmap previews
  have no conditional background. The existing null highlight remains for
  ordinary cells, including missing identifiers.
- [x] Prepare list/array element means in bounded workers with preserved source
  identity, visible diagnostics and unchanged payloads.
- [x] Remove image smoothing in preview reduction and native magnification;
  verify original colors/pixels.
- [x] Full-suite, native and restoration acceptance.

Step 1 passes 17 focused table/record tests, full Pyrefly/Ruff checks and the
native detailed-row smoke. Identifier overrides can be changed reversibly to
Text to enable length shading. Inspect suppresses image/heatmap shading even
for missing values; Table retains its ordinary cell styling. This supersedes
the identifier and Inspect-image color rules recorded in the previous
[row presentation evidence](row-inspection-presentation.md).

Step 2 passes 42 focused presentation, preview, record, nested-column and aligned
NPZ tests, full Pyrefly/Ruff checks, and native container-color, gallery and
detailed-row smokes. Ragged/fixed containers average all finite numeric leaves;
text leaves average Unicode character lengths with Crest. Empty containers are
neutral and nonfinite exclusions are explained in tooltips. Exact NumPy means
are streamed through bounded buffers from worker-owned member leases. Metadata
opening remains decode-free. Table and Inspect share each containing 100-row
Table page's automatic range; custom ranges support comparisons across pages.
Sorting retains source row identity and original payloads remain unchanged.
The native container smoke verifies neutral identifiers, unshaded Inspect image
previews and colored generic arrays. The existing gallery smoke passes with
39 frames, approximately 15.6 ms p95 and 42,848 retained GPU bytes.

Step 3 passes 61 focused reference/image/heatmap/gallery tests, full Pyrefly/Ruff
checks, and native integer/fractional zoom-and-pan framebuffer gates. Both the
production preview cache and original-pixel canvas render the checkerboard with
only its two original colors. A following control texture still has 164/244
interpolated colors, verifying sampling restoration. GPU textures and sampler
objects are disposed with their GUI owners. Thumbnail reduction uses explicit
nearest sampling, with original-palette/source-preservation tests.

The installed [OpenGL backend](https://github.com/ocornut/imgui/blob/v1.92.9/backends/imgui_impl_opengl3.cpp)
overrides per-texture filtering. Bundle's Python
bindings omit draw callbacks, so a narrow Linux OpenGL bridge calls the exported
public `ImDrawList::AddCallback` API with opaque pointers and scopes a nearest
sampler to each image draw. It restores the previous sampler for subsequent
text/plots. No internal ImGui struct layouts are accessed. Rerun the framebuffer
gate when updating ImGui Bundle. These native gates verify Linux Mesa; other
renderers/platforms remain unverified.

The complete native sorted-gallery workflow passes again with 39 frames,
approximately 14.8 ms p95, a 56.3 ms first preview and unchanged GPU budgets.
One preceding run missed its synthetic record-open click; the fresh rerun
verified the input transition and exact original-pixel values.

Final acceptance passes 1,214 tests (three existing PyTorch warnings), full
Pyrefly (zero errors) and Ruff lint/format checks. Detailed Inspect passes in
Dark and Light themes with both image fields visible. The dedicated compressed
NPZ workspace gate saves in 27 frames and restores in a separate process in 26,
preserving selected columns, focused row, custom color range and image viewport.
Sorted source identity, exact element means and original pixel values match in
both processes. The existing whole-session workspace gate also passes (24/31
frames). Sources stay unchanged and neither ML nor playback starts implicitly.

Reproduce the native gates with `LIBGL_ALWAYS_SOFTWARE=1 POLARS_MAX_THREADS=8`
and `uv run python` for:

- `scripts/rebuild_container_colors_smoke.py`
- `scripts/rebuild_image_sampling_smoke.py` (also `--fractional`)
- `scripts/rebuild_container_restore_smoke.py`
- `scripts/rebuild_gallery_smoke.py`
- `scripts/rebuild_row_inspection_smoke.py --mode detail` (Dark and `--theme Light`)
- `scripts/rebuild_workspace_smoke.py`

JSON evidence and checkerboard screenshots are written under `/tmp/datelier-*`.
Existing human listening, Titanic usability and accelerated/platform rendering
assumptions retain their status.
