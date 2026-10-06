"""Narrow lazy PyTorch boundary; app imports do not require the optional extra."""

import importlib
from collections.abc import Callable, Sequence
from contextlib import AbstractContextManager
from pathlib import Path
from typing import Protocol, cast

import numpy as np
from numpy.typing import NDArray


class Device(Protocol):
    @property
    def type(self) -> str: ...


class TensorValue(Protocol):
    @property
    def shape(self) -> Sequence[int]: ...
    @property
    def dtype(self) -> object: ...
    @property
    def layout(self) -> object: ...
    @property
    def device(self) -> Device: ...
    @property
    def is_quantized(self) -> bool: ...
    def stride(self) -> Sequence[int]: ...
    def storage_offset(self) -> int: ...
    def element_size(self) -> int: ...
    def __getitem__(self, selector: tuple[int | slice, ...]) -> TensorValue: ...
    def detach(self) -> TensorValue: ...
    def resolve_conj(self) -> TensorValue: ...
    def resolve_neg(self) -> TensorValue: ...
    def to(self, *, dtype: object) -> TensorValue: ...
    def view(self, dtype: object) -> TensorValue: ...
    def numpy(self) -> NDArray[np.generic]: ...


class TorchRuntime(Protocol):
    @property
    def float32(self) -> object: ...
    @property
    def uint8(self) -> object: ...
    @property
    def uint16(self) -> object: ...
    def is_tensor(self, value: object) -> bool: ...
    def load(
        self, path: Path, *, weights_only: bool, map_location: str, mmap: bool = False
    ) -> object: ...


def require_torch() -> TorchRuntime:
    try:
        # A single typed protocol isolates the dynamically imported optional API.
        return cast(TorchRuntime, importlib.import_module("torch"))
    except ImportError as error:
        raise ValueError(
            "Checkpoint inspection needs the optional CPU PyTorch extra. "
            "Install it with: uv sync --locked --extra checkpoints"
        ) from error


def load_restricted(path: Path, *, metadata: bool, mapped: bool = False) -> object:
    runtime = require_torch()
    try:
        if metadata:
            # PyTorch documents this metadata API despite its private module path.
            module = importlib.import_module("torch._subclasses.fake_tensor")
            factory = cast(
                Callable[[], AbstractContextManager[object]], module.FakeTensorMode
            )
            with factory():
                return runtime.load(
                    path, weights_only=True, map_location="cpu", mmap=False
                )
        return runtime.load(path, weights_only=True, map_location="cpu", mmap=mapped)
    except OSError:
        raise
    except Exception as error:
        # Upstream unpickling errors recommend unrestricted loading/allowlisting.
        # Keep unsupported files diagnostic; never offer or execute those paths.
        raise ValueError(
            "Checkpoint cannot be read with restricted tensor loading. "
            "Export a plain state_dict or a container of tensors "
            "and primitive metadata."
        ) from error
