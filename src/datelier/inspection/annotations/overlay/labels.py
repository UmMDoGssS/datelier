"""Bounded screen-space label occupancy; source boxes and geometry stay intact."""

from math import floor

type LabelRect = tuple[float, float, float, float]


class LabelLayout:
    """Index accepted rectangles by small screen cells, without quadratic scans."""

    def __init__(self) -> None:
        self._cells: dict[tuple[int, int], list[LabelRect]] = {}

    def reserve(self, rect: LabelRect) -> bool:
        x1, y1, x2, y2 = rect
        if x2 <= x1 or y2 <= y1:
            return False
        keys = tuple(
            (x, y)
            for x in range(floor(x1 / 64), floor(x2 / 64) + 1)
            for y in range(floor(y1 / 16), floor(y2 / 16) + 1)
        )
        for key in keys:
            for a1, b1, a2, b2 in self._cells.get(key, ()):
                if x1 < a2 and x2 > a1 and y1 < b2 and y2 > b1:
                    return False
        for key in keys:
            self._cells.setdefault(key, []).append(rect)
        return True
