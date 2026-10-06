"""Pure bounded window planning shared by NumPy arrays and CPU tensors."""

from dataclasses import dataclass
from math import prod

from datelier.inspection.arrays.settings import SliceSettings

MAX_SLICE_CELLS = 16_384
MAX_SLICE_BYTES = 8 * 1024 * 1024


@dataclass(frozen=True)
class WindowPlan:
    axes: tuple[int, ...]
    starts: tuple[int, ...]
    selectors: tuple[int | slice, ...]
    output_shape: tuple[int, ...]
    limited: bool


def plan_window(
    shape: tuple[int, ...], itemsize: int, settings: SliceSettings
) -> WindowPlan:
    settings.validate()
    axes = (
        ()
        if settings.scalar
        else settings.axes or tuple(range(max(0, len(shape) - 2), len(shape)))
    )
    if any(i >= len(shape) for i in axes):
        raise ValueError("Display axis is outside the selected array")
    fixed = settings.fixed or (0,) * len(shape)
    if len(fixed) != len(shape):
        raise ValueError("Provide one fixed position per source axis")
    starts, counts = (
        settings.starts or (0,) * len(axes),
        settings.counts or (128,) * len(axes),
    )
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
    budget = min(MAX_SLICE_CELLS, max(1, MAX_SLICE_BYTES // max(1, itemsize)))
    while sizes and prod(sizes) > budget:
        largest = max(range(len(sizes)), key=lambda i: sizes[i])
        sizes[largest] = max(1, sizes[largest] // 2)
        limited = True
    selectors: list[int | slice] = list(fixed)
    for axis, start, size in zip(axes, starts, sizes, strict=True):
        selectors[axis] = slice(start, start + size)
    output = list(sizes)
    if any(n == 0 for n in shape):
        if output:
            output[0] = 0
        else:
            output = [0]
    return WindowPlan(axes, starts, tuple(selectors), tuple(output), limited)
