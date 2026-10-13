# Container colors and pixel rendering — authorized 2026-10-13

The row presentation refinement makes identifier values neutral, removes
conditional backgrounds from image/heatmap fields in Inspect, and colors
generic arrays/lists by the mean of their elements. Array-backed images and
heatmaps also use element means in Table, where they remain metadata cells.
Images must retain sharp original pixels when enlarged.

- [x] Role/view rules: identifiers stay neutral; Inspect image/heatmap previews
  have no conditional background. The existing null highlight remains for
  ordinary cells, including missing identifiers.
- [ ] Prepare list/array element means in bounded workers with preserved source
  identity, visible diagnostics and unchanged payloads.
- [ ] Remove image smoothing in preview reduction and native magnification;
  verify original colors/pixels.
- [ ] Full-suite, native and restoration acceptance.

Step 1 passes 17 focused table/record tests, full Pyrefly/Ruff checks and the
native detailed-row smoke. Identifier overrides can be changed reversibly to
Text to enable length shading. Inspect suppresses image/heatmap shading even
for missing values; Table retains its ordinary cell styling. This supersedes
the identifier and Inspect-image color rules recorded in the previous
[row presentation evidence](row-inspection-presentation.md).
