"""Native 2D/3D scatter with source-linked picking, brushing, and legends.

Views retain independent heights/axes/cameras; reduction components match the
chosen dimension and require an explicit rerun when incompatible. Native legend
visibility hides both points and their highlights from picking while preserving
table selection. Continuous colors use a color bar; noise, missing, Other, and
unassigned groups retain distinct labels. Ctrl-click toggles; Shift-drag brushes
displayed points. In 3D right-drag rotates, left-drag pans, and the wheel zooms;
camera gestures pause during brushing. Face controls preserve zoom/selection.
"""

from datelier.gui.relationships.scatter.primitives import (
    draw_color_items as draw_color_items,
)
from datelier.gui.relationships.scatter.primitives import item_label as item_label
from datelier.gui.relationships.scatter.primitives import (
    legend_hovered as legend_hovered,
)
from datelier.gui.relationships.scatter.primitives import rgba_color as rgba_color
from datelier.gui.relationships.scatter.primitives import (
    with_color_scale as with_color_scale,
)
from datelier.gui.relationships.scatter.router import ScatterRouter as ScatterRouter
from datelier.gui.relationships.scatter.summary import ScatterSummary as ScatterSummary
from datelier.gui.relationships.scatter.three_dimensional import (
    FACE_VIEWS as FACE_VIEWS,
)
from datelier.gui.relationships.scatter.three_dimensional import (
    CameraFaceChoice as CameraFaceChoice,
)
from datelier.gui.relationships.scatter.three_dimensional import (
    CameraState as CameraState,
)
from datelier.gui.relationships.scatter.three_dimensional import (
    NativeScatter3D as NativeScatter3D,
)
from datelier.gui.relationships.scatter.three_dimensional import (
    ProjectedInput as ProjectedInput,
)
from datelier.gui.relationships.scatter.three_dimensional import (
    Scatter3DPlot as Scatter3DPlot,
)
from datelier.gui.relationships.scatter.two_dimensional import (
    NativeScatter2D as NativeScatter2D,
)
from datelier.gui.relationships.scatter.two_dimensional import (
    ScatterInput as ScatterInput,
)
from datelier.gui.relationships.scatter.two_dimensional import (
    ScatterPlot as ScatterPlot,
)
