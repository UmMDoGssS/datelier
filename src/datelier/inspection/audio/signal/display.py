"""Independent display scale/colors derived from immutable original-unit power."""

import numpy as np
from numpy.typing import NDArray

from datelier.inspection.audio.signal.types import (
    SignalViewSettings,
    SpectralTile,
    SpectrumScale,
)
from datelier.inspection.heatmaps import normalize, ramp_colors


def spectral_display(
    power: NDArray[np.float64], settings: SignalViewSettings
) -> tuple[NDArray[np.float64], tuple[SpectralTile, ...], tuple[float, float]]:
    values = (
        power
        if settings.scale == SpectrumScale.POWER
        else np.maximum(
            10 * np.log10(np.maximum(power, 10 ** (settings.db_floor / 10))),
            settings.db_floor,
        )
    )
    normalized = normalize(values, settings.color_range)
    bounds = normalized.display_range
    assert bounds is not None
    rgba = ramp_colors(normalized.colors, settings.colormap)
    tiles: list[SpectralTile] = []
    # Full frequency grids can exceed hardware texture dimensions. Bounded tiles
    # retain every color cell, with no additional frequency downsampling.
    for row in range(0, rgba.shape[0], 2048):
        for column in range(0, rgba.shape[1], 2048):
            colors = rgba[row : row + 2048, column : column + 2048].copy()
            colors.flags.writeable = False
            tiles.append(SpectralTile(row, column, colors))
    values.flags.writeable = False
    return values, tuple(tiles), (float(bounds[0]), float(bounds[1]))
