"""Worker-only leases over restricted CPU checkpoint storage."""

from collections.abc import Callable, Generator, Mapping
from concurrent.futures import CancelledError
from contextlib import contextmanager
from threading import Event, RLock
from typing import cast

from datelier.inspection.checkpoints import CheckpointCatalog
from datelier.io.checkpoints.runtime import TensorValue, load_restricted, require_torch


class CheckpointStore:
    def __init__(self, retained_bytes: int = 256 * 1024 * 1024) -> None:
        if retained_bytes < 0:
            raise ValueError("Checkpoint retention bytes must be nonnegative")
        self.limit = retained_bytes
        self._lock = RLock()
        self._stop = Event()
        self._catalog: CheckpointCatalog | None = None
        self._value: object = None
        self._leases = 0
        self.stored_bytes = 0
        self.loads = 0

    @staticmethod
    def check_source(catalog: CheckpointCatalog) -> None:
        reference = catalog.source
        current = reference.path.stat()
        if (current.st_size, current.st_mtime_ns) != (
            reference.size_bytes,
            reference.modified_ns,
        ):
            raise ValueError("Checkpoint source changed; reload its metadata")

    def _check(self, stopped: Callable[[], bool] | None) -> None:
        if self._stop.is_set() or stopped is not None and stopped():
            raise CancelledError("Tensor preparation abandoned")

    @contextmanager
    def open_tensor(
        self,
        catalog: CheckpointCatalog,
        name: str,
        stopped: Callable[[], bool] | None = None,
    ) -> Generator[TensorValue]:
        info = catalog.tensor(name)
        if info.diagnostic:
            raise ValueError(info.diagnostic)
        with self._lock:
            self._check(stopped)
            self.check_source(catalog)
            if self._catalog is None or self._catalog.source != catalog.source:
                value = load_restricted(
                    catalog.source.path, metadata=False, mapped=catalog.mapped
                )
                try:
                    self._check(stopped)
                    self.check_source(catalog)
                except BaseException:
                    # Cancel/error tracebacks must not pin newly read storage.
                    value = None
                    raise
                self._value, self._catalog = value, catalog
                self.stored_bytes = sum(t.raw_bytes for t in catalog.tensors)
                self.loads += 1
            value = self._value
            for key in info.path:
                if isinstance(value, Mapping):
                    value = cast(Mapping[str | int, object], value)[key]
                elif isinstance(value, (list, tuple)) and type(key) is int:
                    value = cast(list[object] | tuple[object, ...], value)[key]
                else:
                    raise ValueError("Tensor path no longer matches the checkpoint")
            if not require_torch().is_tensor(value):
                raise ValueError("Tensor path no longer contains a tensor")
            tensor = cast(TensorValue, value)
            if tensor.device.type != "cpu" or (
                tuple(tensor.shape),
                str(tensor.dtype),
                str(tensor.layout),
            ) != (info.shape, info.dtype, info.layout):
                raise ValueError("Loaded CPU tensor differs from its metadata")
            self._leases += 1
        try:
            self._check(stopped)
            yield tensor
            self._check(stopped)
            self.check_source(catalog)
        finally:
            with self._lock:
                self._leases -= 1
                self._trim()

    def _trim(self) -> None:
        if not self._leases and (self.stored_bytes > self.limit or self._stop.is_set()):
            self._value, self._catalog = None, None
            self.stored_bytes = 0

    def trim(self) -> None:
        with self._lock:
            self._trim()

    def abandon(self) -> None:
        self._stop.set()

    def close(self) -> None:
        self.abandon()
        self.trim()
