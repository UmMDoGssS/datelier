"""Exact bounded array windows and display-only numeric preparation."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import cast

import numpy as np
from numpy.typing import NDArray

from datelier.inspection.arrays.settings import SliceSettings as SliceSettings
from datelier.inspection.arrays.types import ArrayCatalog
from datelier.inspection.arrays.windows import MAX_SLICE_BYTES as MAX_SLICE_BYTES
from datelier.inspection.arrays.windows import MAX_SLICE_CELLS as MAX_SLICE_CELLS
from datelier.inspection.arrays.windows import plan_window
from datelier.inspection.heatmaps import normalize
from datelier.io.arrays import ArrayStore


@dataclass(frozen=True)
class PreparedSlice:
    settings: SliceSettings
    source_shape: tuple[int, ...]
    axes: tuple[int, ...]
    starts: tuple[int, ...]
    raw: NDArray[np.generic]
    cells: tuple[tuple[str, ...], ...]
    numeric: NDArray[np.float64] | None
    colors: NDArray[np.float64] | None
    finite_range: tuple[int | float, int | float] | None
    nonfinite: int
    limited: bool
    heatmap: NDArray[np.float64] | None = None
    nonfinite_spans: tuple[tuple[int, int, int], ...] = ()
    diagnostic: str = ""

    @property
    def retained_bytes(self) -> int:
        return (
            self.raw.nbytes
            + (self.numeric.nbytes if self.numeric is not None else 0)
            + (self.colors.nbytes if self.colors is not None else 0)
            + (self.heatmap.nbytes if self.heatmap is not None else 0)
            + sum(len(cell.encode("utf8")) for row in self.cells for cell in row)
        )


def _numeric(
    raw: NDArray[np.generic], settings: SliceSettings
) -> tuple[
    NDArray[np.float64] | None,
    NDArray[np.float64] | None,
    tuple[int | float, int | float] | None,
    int,
]:
    chosen = raw
    if settings.field is not None:
        if raw.dtype.names is None or settings.field not in raw.dtype.names:
            raise ValueError("Selected structured field is unavailable")
        # NumPy's named-field overload applies to a structured void dtype.
        chosen = cast(NDArray[np.generic], cast(NDArray[np.void], raw)[settings.field])
        if chosen.ndim != raw.ndim:
            return None, None, None, 0
    if chosen.dtype.kind not in "biufc":
        return None, None, None, 0
    if chosen.dtype.kind == "c":
        chosen = (
            np.abs(chosen)
            if settings.component == "Magnitude"
            else chosen.real
            if settings.component == "Real"
            else chosen.imag
        )
    numeric = np.array(chosen, dtype=np.float64, copy=True)
    normalized = normalize(chosen, settings.value_range)
    finite = np.isfinite(numeric)
    numeric[~finite] = np.nan
    # ImPlot's ndarray binding requires writable presentation buffers even
    # though drawing does not edit them. Raw authoritative values stay read-only.
    return numeric, normalized.colors, normalized.bounds, normalized.nonfinite


def prepare_slice(
    store: ArrayStore,
    catalog: ArrayCatalog,
    settings: SliceSettings,
    cancelled: Callable[[], bool] | None = None,
) -> PreparedSlice:
    member = catalog.member(settings.member)
    shape = member.shape
    itemsize = member.dtype.itemsize if member.dtype is not None else 1
    window = plan_window(shape, itemsize, settings)
    axes, starts = window.axes, window.starts
    with store.open_member(catalog, settings.member, cancelled) as array:
        if any(n == 0 for n in shape):
            raw = cast(
                NDArray[np.generic], np.empty(window.output_shape, dtype=array.dtype)
            )
        else:
            selected = np.asarray(array[window.selectors])
            if axes:
                selected = selected.transpose(
                    tuple(sorted(axes).index(axis) for axis in axes)
                )
            raw = cast(NDArray[np.generic], selected.copy())
    return prepare_array_display(raw, settings, shape, axes, starts, window.limited)


def prepare_array_display(
    raw: NDArray[np.generic],
    settings: SliceSettings,
    shape: tuple[int, ...],
    axes: tuple[int, ...],
    starts: tuple[int, ...],
    limited: bool,
    *,
    diagnostic: str = "",
) -> PreparedSlice:
    """Prepare numeric buffers and readable cells from an already bounded copy."""
    raw.flags.writeable = False
    matrix = (
        raw.reshape((0, 1))
        if raw.size == 0
        else raw.reshape((1, 1))
        if not axes
        else raw.reshape((-1, 1))
        if len(axes) == 1
        else raw
    )

    def display(value: object) -> str:
        text = str(value).replace("\r", "\\r").replace("\n", "\\n").replace("\t", "\\t")
        return text if len(text) <= 256 else text[:256] + "… (truncated)"

    cells = tuple(tuple(display(value) for value in row) for row in matrix)
    numeric, colors, bounds, nonfinite = _numeric(raw, settings)
    heatmap: NDArray[np.float64] | None = None
    spans: list[tuple[int, int, int]] = []
    if colors is not None and colors.ndim == 2:
        heatmap = np.nan_to_num(colors[::-1], nan=0.0).copy()
        for row, values in enumerate(colors):
            start: int | None = None
            for column, value in enumerate(values):
                if not np.isfinite(value) and start is None:
                    start = column
                elif np.isfinite(value) and start is not None:
                    spans.append((row, start, column - start))
                    start = None
            if start is not None:
                spans.append((row, start, len(values) - start))
    return PreparedSlice(
        settings,
        shape,
        axes,
        starts,
        raw,
        cells,
        numeric,
        colors,
        bounds,
        nonfinite,
        limited,
        heatmap,
        tuple(spans),
        "; ".join(
            filter(
                None,
                (
                    diagnostic,
                    "Plots require a scalar numeric dtype/field; "
                    "raw values remain available."
                    if numeric is None
                    else "",
                ),
            )
        ),
    )
