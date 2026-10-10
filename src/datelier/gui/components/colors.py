"""Register display-only color ramps shared by numeric plot components."""

import numpy as np
from imgui_bundle import implot

from datelier.inspection.heatmaps import RAMPS, Colormap


def native_colormap(colormap: Colormap) -> int:
    name = "Datelier " + colormap.value
    index = implot.get_colormap_index(name)
    if index < 0:
        # Register the same linear stops used by worker RGBA preparation.
        colors = np.asarray([(*rgb, 1) for rgb in RAMPS[colormap]], dtype=np.float32)
        index = implot.add_colormap(name, colors, False)
    return index
