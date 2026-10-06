"""Exact bounded CPU tensor copies and explicit display-only dtype conversion."""

from collections.abc import Callable
from dataclasses import dataclass
from math import prod

import numpy as np
from numpy.typing import NDArray

from datelier.inspection.arrays.settings import SliceSettings
from datelier.inspection.arrays.slices import PreparedSlice, prepare_array_display
from datelier.inspection.arrays.windows import plan_window
from datelier.inspection.checkpoints.types import CheckpointCatalog
from datelier.io.checkpoints.runtime import require_torch
from datelier.io.checkpoints.storage import CheckpointStore


@dataclass(frozen=True)
class PreparedTensorSlice:
    view: PreparedSlice
    dtype: str
    storage: PreparedSlice | None = None

    @property
    def retained_bytes(self) -> int:
        return self.view.retained_bytes + (
            self.storage.retained_bytes if self.storage is not None else 0
        )


def prepare_tensor_slice(
    store: CheckpointStore,
    catalog: CheckpointCatalog,
    settings: SliceSettings,
    cancelled: Callable[[], bool] | None = None,
) -> PreparedTensorSlice:
    info = catalog.tensor(settings.member)
    if settings.field is not None:
        raise ValueError("Tensors do not have NumPy structured fields")
    runtime = require_torch()
    count = prod(info.shape)
    window = plan_window(info.shape, max(1, info.raw_bytes // max(1, count)), settings)
    bits: NDArray[np.generic] | None = None
    diagnostic = ""
    with store.open_tensor(catalog, settings.member, cancelled) as tensor:
        selected = (
            tensor if any(n == 0 for n in info.shape) else tensor[window.selectors]
        )
        selected = selected.detach().resolve_conj().resolve_neg()
        if info.dtype == "torch.bfloat16" or info.dtype.startswith("torch.float8"):
            bits = (
                selected.view(
                    runtime.uint16 if info.dtype == "torch.bfloat16" else runtime.uint8
                )
                .numpy()
                .copy()
            )
            raw = selected.to(dtype=runtime.float32).numpy().copy()
            diagnostic = (
                f"{info.dtype} values shown exactly as Float32; "
                "original storage bits remain available separately."
            )
        else:
            raw = selected.numpy().copy()
        if any(n == 0 for n in info.shape):
            raw = raw.reshape(window.output_shape)
            if bits is not None:
                bits = bits.reshape(window.output_shape)
        elif window.axes:
            order = tuple(sorted(window.axes).index(axis) for axis in window.axes)
            raw = raw.transpose(order)
            if bits is not None:
                bits = bits.transpose(order)
    view = prepare_array_display(
        raw,
        settings,
        info.shape,
        window.axes,
        window.starts,
        window.limited,
        diagnostic=diagnostic,
    )
    storage = (
        prepare_array_display(
            bits,
            settings,
            info.shape,
            window.axes,
            window.starts,
            window.limited,
            diagnostic=(
                "Original tensor storage bits; integer values do not represent "
                "the displayed numeric magnitude."
            ),
        )
        if bits is not None
        else None
    )
    return PreparedTensorSlice(view, info.dtype, storage)
