"""Pure bounded screen-space selection geometry for plotted points."""

import numpy as np
from numpy.typing import NDArray


def projected_nearest(
    pixels: NDArray[np.float64], depths: NDArray[np.float64], mouse: tuple[float, float]
) -> int | None:
    if not len(pixels) or not np.isfinite(mouse).all():
        return None
    with np.errstate(over="ignore", invalid="ignore"):
        distances = ((pixels - mouse) ** 2).sum(axis=1)
    valid = np.isfinite(distances) & np.isfinite(depths) & (distances <= 64)
    indices = np.flatnonzero(valid)
    if not len(indices):
        return None
    # Frontmost along the picking ray wins projected ties; subpixel rounding
    # avoids floating noise choosing an obscured duplicate point.
    order = np.lexsort((depths[indices], np.round(distances[indices], 3)))
    return int(indices[order[0]])


def projected_rectangle(
    pixels: NDArray[np.float64], start: tuple[float, float], end: tuple[float, float]
) -> NDArray[np.bool_]:
    return (
        np.isfinite(pixels).all(axis=1)
        & (pixels[:, 0] >= min(start[0], end[0]))
        & (pixels[:, 0] <= max(start[0], end[0]))
        & (pixels[:, 1] >= min(start[1], end[1]))
        & (pixels[:, 1] <= max(start[1], end[1]))
    )
