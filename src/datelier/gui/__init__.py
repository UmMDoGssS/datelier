"""Native ImGui/ImPlot presentation assembled from injected component families.

Components render immediate children from prepared state; leaf widgets receive
narrow controllers/bindings/commands. Whole editor/file controllers stay at the
bootstrap/composition boundary. Pre-frame polling coordinates workers; file
reads, table-wide statistics, and fitting never belong in frame callbacks.
Native font loading and GPU texture ownership remain on the GUI thread.

Automated replacement-GUI acceptance does not close the unfinished Titanic human
usability review. It still needs unaided import/missingness, readable chart/legend,
grouped survival, explicit PCA/exclusions, filter/undo/brush, and save/export/relink
workflows across sizes/themes. Proposed timings from the historical review are
targets, not measured results. Accelerated rendering and other platforms remain
unverified; native Linux verification uses Mesa software OpenGL.
"""
