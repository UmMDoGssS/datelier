"""Original-pixel file/array inspection and explicit collection profiles.

Prepared windows retain raw dtype values, oriented coordinates, display buffers,
and labeled overview strides. Zoom can request source pixels beyond an overview.
Numeric heatmaps share this path with explicit channels/fixed-axis slices;
colormaps and value ranges are display-only. File/view/source-row locators keep
image records and annotation geometry aligned through sorting and restoration.
"""
