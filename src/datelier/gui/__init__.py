"""Native ImGui/ImPlot presentation assembled from injected component families.

Components render immediate children from prepared state; leaf widgets receive
narrow controllers/bindings/commands. Whole editor/file controllers stay at the
bootstrap/composition boundary. Pre-frame polling coordinates workers; file
reads, table-wide statistics, and fitting never belong in frame callbacks.
Native font loading and GPU texture ownership remain on the GUI thread.

The Titanic human usability review remains a known 1.0 limitation, deferred by
the user on 2026-10-22. It requires unaided workflows: find
size/age missingness within 30 seconds, sex counts within 15, switch distributions
in one change, resize within 5, and produce colored age/fare and grouped survival
within 30 seconds. Also verify explicit PCA/exclusions, filter/undo/brush, and
save/export/relink. At 1280x800, chart focus targets 340 pixels including axes and
table focus ten rows. Repeat at 1024x768, 1280x800, and 1600x1000 across themes.
These are unmeasured acceptance targets; automated feature gates do not close
them. Accelerated rendering and other platforms remain unverified; native Linux
verification uses Mesa software OpenGL.
"""
