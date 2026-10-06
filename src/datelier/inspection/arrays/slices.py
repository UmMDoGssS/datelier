"""Exact bounded array windows and display-only numeric preparation."""

from collections.abc import Callable
from dataclasses import dataclass
from math import prod
from typing import cast

import numpy as np
from numpy.typing import NDArray

from datelier.inspection.arrays.types import ArrayCatalog
from datelier.io.arrays.storage import ArrayStore

MAX_SLICE_CELLS = 16_384
MAX_SLICE_BYTES = 8 * 1024 * 1024


@dataclass(frozen=True)
class SliceSettings:
    member: str = "$"
    axes: tuple[int, ...] = ()
    fixed: tuple[int, ...] = ()
    starts: tuple[int, ...] = ()
    counts: tuple[int, ...] = ()
    field: str | None = None
    component: str = "Magnitude"

    def validate(self) -> None:
        if len(self.axes) > 2 or len(set(self.axes)) != len(self.axes):
            raise ValueError("Choose one or two distinct display axes")
        if any(i < 0 for i in (*self.axes, *self.fixed, *self.starts)):
            raise ValueError("Array axes/indices must be nonnegative")
        if len(self.fixed) > 64 or len(self.starts) > 2 or len(self.counts) > 2:
            raise ValueError("Array slice settings exceed dimension bounds")
        if any(not 1 <= n <= 4096 for n in self.counts):
            raise ValueError(
                "Slice windows contain between 1 and 4096 positions per axis"
            )
        if self.component not in ("Magnitude", "Real", "Imaginary"):
            raise ValueError("Unknown complex display component")


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
    finite_range: tuple[float, float] | None
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
    tuple[float, float] | None,
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
    finite = np.isfinite(numeric)
    count = numeric.size - int(np.count_nonzero(finite))
    colors = np.full(numeric.shape, np.nan, dtype=np.float64)
    bounds: tuple[float, float] | None = None
    if np.any(finite):
        lo, hi = float(numeric[finite].min()), float(numeric[finite].max())
        bounds = (lo, hi)
        if lo == hi:
            colors[finite] = 0.5
        else:
            scale = max(abs(lo), abs(hi), 1.0)
            denominator = hi / scale - lo / scale
            colors[finite] = (numeric[finite] / scale - lo / scale) / denominator
    numeric[~finite] = np.nan
    # ImPlot's ndarray binding requires writable presentation buffers even
    # though drawing does not edit them. Raw authoritative values stay read-only.
    colors.flags.writeable = False
    return numeric, colors, bounds, count


def prepare_slice(
    store: ArrayStore,
    catalog: ArrayCatalog,
    settings: SliceSettings,
    cancelled: Callable[[], bool] | None = None,
) -> PreparedSlice:
    settings.validate()
    member = catalog.member(settings.member)
    shape = member.shape
    axes = settings.axes or tuple(range(max(0, len(shape) - 2), len(shape)))
    if any(i >= len(shape) for i in axes):
        raise ValueError("Display axis is outside the selected array")
    fixed = settings.fixed or (0,) * len(shape)
    if len(fixed) != len(shape):
        raise ValueError("Provide one fixed position per source axis")
    starts = settings.starts or (0,) * len(axes)
    counts = settings.counts or (128,) * len(axes)
    if len(starts) != len(axes) or len(counts) != len(axes):
        raise ValueError("Provide one window start/count per display axis")
    if any(
        start >= shape[axis] and shape[axis] != 0
        for axis, start in zip(axes, starts, strict=True)
    ):
        raise ValueError("Window start is outside the selected array")
    if any(
        position >= shape[i] and shape[i] != 0
        for i, position in enumerate(fixed)
        if i not in axes
    ):
        raise ValueError("Fixed position is outside the selected array")
    sizes = [
        min(count, max(0, shape[axis] - start))
        for axis, start, count in zip(axes, starts, counts, strict=True)
    ]
    limited = any(size < shape[axis] for axis, size in zip(axes, sizes, strict=True))
    itemsize = member.dtype.itemsize if member.dtype is not None else 1
    budget = min(MAX_SLICE_CELLS, max(1, MAX_SLICE_BYTES // max(1, itemsize)))
    while sizes and prod(sizes) > budget:
        largest = max(range(len(sizes)), key=lambda i: sizes[i])
        sizes[largest] = max(1, sizes[largest] // 2)
        limited = True
    selectors: list[int | slice] = list(fixed)
    for axis, start, size in zip(axes, starts, sizes, strict=True):
        selectors[axis] = slice(start, start + size)
    with store.open_member(catalog, settings.member, cancelled) as array:
        if any(n == 0 for n in shape):
            output_shape = list(sizes)
            if output_shape:
                output_shape[0] = 0
            raw = cast(
                NDArray[np.generic], np.empty(tuple(output_shape), dtype=array.dtype)
            )
        else:
            selected = np.asarray(array[tuple(selectors)])
            if axes:
                selected = selected.transpose(
                    tuple(sorted(axes).index(axis) for axis in axes)
                )
            raw = cast(NDArray[np.generic], selected.copy())
    raw.flags.writeable = False
    matrix = (
        raw.reshape((1, 1))
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
        "Plots require a scalar numeric dtype/field; raw values remain available."
        if numeric is None
        else "",
    )
