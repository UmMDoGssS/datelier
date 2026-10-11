"""Bounded, revision-bound source-row selection shared by tables and plots."""

import math
from collections.abc import Iterable
from dataclasses import dataclass, field

import numpy as np
from numpy.typing import NDArray

from datelier.core import DatasetRevision
from datelier.plotting.scatter.prepare import Scatter

SELECTION_LIMIT = 10_000
Coordinates = tuple[NDArray[np.float64], NDArray[np.float64]]


@dataclass
class LinkedSelection:
    revision: DatasetRevision | None = None
    row_ids: frozenset[int] = frozenset()
    version: int = 0
    message: str = ""
    _partitions: dict[
        int, tuple[Scatter, Coordinates, Coordinates, NDArray[np.bool_]]
    ] = field(default_factory=dict)

    def bind(self, revision: DatasetRevision) -> None:
        if revision != self.revision:
            self.revision = revision
            self.row_ids = frozenset()
            self.version += 1
            self._partitions.clear()
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
        self._partitions.clear()
        self.message = f"{len(chosen):,} source rows selected."
        return True

    def rectangle(
        self,
        points: Scatter,
        x1: float,
        y1: float,
        x2: float,
        y2: float,
        *,
        visible: NDArray[np.bool_] | None = None,
    ) -> bool:
        mask = (
            (points.x >= min(x1, x2))
            & (points.x <= max(x1, x2))
            & (points.y >= min(y1, y2))
            & (points.y <= max(y1, y2))
        )
        if visible is not None:
            mask &= visible
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
        if (
            not all(math.isfinite(value) for value in (x, y, x_scale, y_scale))
            or x_scale <= 0
            or y_scale <= 0
        ):
            return None
        with np.errstate(over="ignore", invalid="ignore"):
            distances = ((points.x - x) * x_scale) ** 2 + (
                (points.y - y) * y_scale
            ) ** 2
        distances = np.where(np.isfinite(distances), distances, np.inf)
        index = int(np.argmin(distances))
        if distances[index] > 64:  # Eight screen pixels, independent of zoom.
            return None
        if self.choose(points.revision, (int(points.row_ids[index]),), toggle=toggle):
            return int(points.positions[index])
        return None

    def overlay(
        self, points: Scatter
    ) -> tuple[NDArray[np.float64], NDArray[np.float64]]:
        key = id(points)
        cached = self._partitions.get(key)
        if cached is None:
            ids = self.row_ids if points.revision == self.revision else frozenset()
            mask = np.fromiter(
                (int(i) in ids for i in points.row_ids), dtype=bool, count=len(points.x)
            )
            overlay = (points.x[mask], points.y[mask])
            unselected = (
                (points.x[~mask], points.y[~mask]) if ids else (points.x, points.y)
            )
            # Enough for every bounded grid cell plus raw/reduced plots. Retain
            # the object with its identity key to prevent Python ID reuse.
            if len(self._partitions) >= 128:
                self._partitions.clear()
            mask.setflags(write=False)
            cached = (points, overlay, unselected, mask)
            self._partitions[key] = cached
        return cached[1]

    def unselected(
        self, points: Scatter
    ) -> tuple[NDArray[np.float64], NDArray[np.float64]]:
        self.overlay(points)
        return self._partitions[id(points)][2]

    def mask(self, points: Scatter) -> NDArray[np.bool_]:
        """Read-only highlights cached with their revision and selected row set."""
        self.overlay(points)
        return self._partitions[id(points)][3]
