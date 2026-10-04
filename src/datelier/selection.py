"""Bounded, revision-bound source-row selection shared by tables and plots."""

from collections.abc import Iterable
from dataclasses import dataclass, field

import numpy as np
from numpy.typing import NDArray

from datelier.dataset import DatasetRevision
from datelier.plotting import Scatter

SELECTION_LIMIT = 10_000


@dataclass
class LinkedSelection:
    revision: DatasetRevision | None = None
    row_ids: frozenset[int] = frozenset()
    version: int = 0
    message: str = ""
    _overlay_points: Scatter | None = None
    _overlay_version: int = -1
    _overlay: tuple[NDArray[np.float64], NDArray[np.float64]] = field(
        default_factory=lambda: (
            np.array([], dtype=np.float64),
            np.array([], dtype=np.float64),
        )
    )

    def bind(self, revision: DatasetRevision) -> None:
        if revision != self.revision:
            self.revision = revision
            self.row_ids = frozenset()
            self.version += 1
            self._overlay_points = None
            self.message = "Selection cleared for the new dataset revision."

    def choose(
        self, revision: DatasetRevision, ids: Iterable[int], *, toggle: bool = False
    ) -> bool:
        if revision != self.revision:
            return False
        chosen: set[int] = set()
        for row_id in ids:
            chosen.add(row_id)
            if len(chosen) > SELECTION_LIMIT:
                raise ValueError("Selection is limited to 10,000 displayed rows")
        if toggle:
            chosen = set(self.row_ids) ^ chosen
        if len(chosen) > SELECTION_LIMIT:
            self.message = "Selection limit reached (10,000 rows)."
            return False
        self.row_ids = frozenset(chosen)
        self.version += 1
        self.message = f"{len(chosen):,} source rows selected."
        return True

    def rectangle(
        self, points: Scatter, x1: float, y1: float, x2: float, y2: float
    ) -> bool:
        mask = (
            (points.x >= min(x1, x2))
            & (points.x <= max(x1, x2))
            & (points.y >= min(y1, y2))
            & (points.y <= max(y1, y2))
        )
        return self.choose(points.revision, (int(i) for i in points.row_ids[mask]))

    def nearest(
        self,
        points: Scatter,
        x: float,
        y: float,
        x_scale: float,
        y_scale: float,
        *,
        toggle: bool = False,
    ) -> int | None:
        if points.revision != self.revision or not len(points.x):
            return None
        distances = ((points.x - x) * x_scale) ** 2 + ((points.y - y) * y_scale) ** 2
        index = int(np.argmin(distances))
        if distances[index] > 64:  # Eight screen pixels, independent of zoom.
            return None
        if self.choose(points.revision, (int(points.row_ids[index]),), toggle=toggle):
            return int(points.positions[index])
        return None

    def overlay(
        self, points: Scatter
    ) -> tuple[NDArray[np.float64], NDArray[np.float64]]:
        if points is not self._overlay_points or self.version != self._overlay_version:
            ids = self.row_ids if points.revision == self.revision else frozenset()
            mask = np.isin(points.row_ids, tuple(ids))
            self._overlay = (points.x[mask], points.y[mask])
            self._overlay_points = points
            self._overlay_version = self.version
        return self._overlay
