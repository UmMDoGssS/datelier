"""EXIF transforms in continuous image-edge coordinates and array views."""

import numpy as np
from numpy.typing import NDArray


def oriented_point(
    x: float, y: float, width: int, height: int, orientation: int
) -> tuple[float, float]:
    return {
        1: (x, y),
        2: (width - x, y),
        3: (width - x, height - y),
        4: (x, height - y),
        5: (y, x),
        6: (height - y, x),
        7: (height - y, width - x),
        8: (y, width - x),
    }.get(orientation, (x, y))


def source_pixel(
    x: int, y: int, width: int, height: int, orientation: int
) -> tuple[int, int]:
    """Invert a displayed pixel centre, avoiding the edge/pixel off-by-one."""
    inverse = {6: 8, 8: 6}.get(orientation, orientation)
    w, h = (height, width) if orientation in (5, 6, 7, 8) else (width, height)
    sx, sy = oriented_point(x + 0.5, y + 0.5, w, h, inverse)
    return int(sx), int(sy)


def orient_array(raw: NDArray[np.generic], orientation: int) -> NDArray[np.generic]:
    match orientation:
        case 2:
            return raw[:, ::-1]
        case 3:
            return raw[::-1, ::-1]
        case 4:
            return raw[::-1]
        case 5:
            return raw.swapaxes(0, 1)
        case 6:
            return np.rot90(raw, -1, axes=(0, 1))
        case 7:
            return raw.swapaxes(0, 1)[::-1, ::-1]
        case 8:
            return np.rot90(raw, 1, axes=(0, 1))
        case _:
            return raw
