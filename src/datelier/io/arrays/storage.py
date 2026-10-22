"""Worker-only selected NPZ extraction and read-only mapped member leases."""

from collections import OrderedDict
from collections.abc import Callable, Generator
from concurrent.futures import CancelledError
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from tempfile import NamedTemporaryFile, TemporaryDirectory
from threading import Event, RLock
from typing import cast
from zipfile import ZipFile

import numpy as np
from numpy.typing import NDArray

from datelier.core import SourceReference
from datelier.inspection.arrays import ArrayCatalog, ArrayMember
from datelier.io.arrays.metadata import inspect_arrays

CHUNK_BYTES = 1024 * 1024


@dataclass
class StoredMember:
    path: Path
    size: int
    leases: int = 0


class ArrayStore:
    """Open/release/cleanup on workers. Abandon only sets a thread-safe flag.

    Retention limits do not cap inspectable array size. Oversized members use
    temporary storage while leased and are discarded after the lease. Closing
    defers directory removal until preparing work and mapped leases release it.
    """

    def __init__(
        self, *, retained_bytes: int = 256 * 1024 * 1024, directory: Path | None = None
    ) -> None:
        if retained_bytes < 0:
            raise ValueError("Array retention bytes must be nonnegative")
        self.limit = retained_bytes
        self.directory = directory
        self.stop = Event()
        self._lock = RLock()
        self._temporary: TemporaryDirectory[str] | None = None
        self._entries: OrderedDict[tuple[SourceReference, str], StoredMember] = (
            OrderedDict()
        )
        self._preparing = 0
        self.extractions = 0
        self.extracted_bytes = 0
        self._progress: tuple[str, int, int] | None = None
        self._stored_bytes = 0

    @property
    def progress(self) -> tuple[str, int, int] | None:
        return self._progress

    @property
    def temporary_path(self) -> Path | None:
        temporary = self._temporary
        return Path(temporary.name) if temporary else None

    @property
    def stored_bytes(self) -> int:
        return self._stored_bytes

    def abandon(self) -> None:
        self.stop.set()

    def _check(self, stopped: Callable[[], bool] | None) -> None:
        if self.stop.is_set() or stopped is not None and stopped():
            raise CancelledError("Array preparation abandoned")

    @staticmethod
    def check_source(catalog: ArrayCatalog) -> None:
        source = catalog.source
        current = source.path.stat()
        if (current.st_size, current.st_mtime_ns) != (
            source.size_bytes,
            source.modified_ns,
        ):
            raise ValueError("Array source changed; reload its metadata")

    def _prepare(
        self,
        catalog: ArrayCatalog,
        member: ArrayMember,
        stopped: Callable[[], bool] | None,
    ) -> StoredMember:
        assert member.storage_name is not None
        with self._lock:
            self._check(stopped)
            if self._temporary is None:
                self._temporary = TemporaryDirectory(
                    prefix="datelier-arrays-", dir=self.directory
                )
            directory = self._temporary.name
            self._preparing += 1
            self._progress = (member.name, 0, member.container_bytes)
        path: Path | None = None
        try:
            self.check_source(catalog)
            with NamedTemporaryFile(
                dir=directory, suffix=".npy", delete=False
            ) as output:
                path = Path(output.name)
                count = 0
                with (
                    ZipFile(catalog.source.path) as archive,
                    archive.open(member.storage_name) as stream,
                ):
                    while True:
                        self._check(stopped)
                        chunk = stream.read(CHUNK_BYTES)
                        if not chunk:
                            break
                        output.write(chunk)
                        count += len(chunk)
                        with self._lock:
                            self._progress = (
                                member.name,
                                count,
                                member.container_bytes,
                            )
            self._check(stopped)
            self.check_source(catalog)
            actual = inspect_arrays(path).members[0]
            if (
                count != member.container_bytes
                or (actual.shape, actual.dtype, actual.fortran_order)
                != (member.shape, member.dtype, member.fortran_order)
                or not actual.usable
            ):
                raise ValueError(
                    "Selected array member differs from its metadata; reload it"
                )
            with self._lock:
                self.extractions += 1
                self.extracted_bytes += count
            return StoredMember(path, count)
        except BaseException:
            if path is not None:
                path.unlink(missing_ok=True)
            raise
        finally:
            with self._lock:
                self._preparing -= 1
                if not self._preparing:
                    self._progress = None
                self._cleanup()

    @contextmanager
    def open_member(
        self,
        catalog: ArrayCatalog,
        name: str,
        stopped: Callable[[], bool] | None = None,
    ) -> Generator[NDArray[np.generic]]:
        self._check(stopped)
        self.check_source(catalog)
        member = catalog.member(name)
        if not member.usable or member.dtype is None:
            raise ValueError(member.diagnostic or "Array dtype is unavailable")
        key = (catalog.source, name)
        entry: StoredMember | None = None
        path = catalog.source.path
        if member.storage_name is not None:
            with self._lock:
                entry = self._entries.get(key)
                if entry is not None:
                    entry.leases += 1
                    self._entries.move_to_end(key)
            if entry is None:
                prepared = self._prepare(catalog, member, stopped)
                with self._lock:
                    try:
                        self._check(stopped)
                    except CancelledError:
                        prepared.path.unlink(missing_ok=True)
                        self._cleanup()
                        raise
                    entry = self._entries.get(key)
                    if entry is None:
                        entry = prepared
                        self._entries[key] = entry
                        self._stored_bytes += entry.size
                    else:
                        prepared.path.unlink(missing_ok=True)
                    entry.leases += 1
                    self._trim()
            path = entry.path
        mapped: np.memmap | None = None
        try:
            self._check(stopped)
            if member.raw_bytes == 0:
                array = cast(
                    NDArray[np.generic], np.empty(member.shape, dtype=member.dtype)
                )
                array.flags.writeable = False
            else:
                mapped = np.memmap(
                    path,
                    mode="r",
                    dtype=member.dtype,
                    offset=member.header_bytes,
                    shape=member.shape,
                    order="F" if member.fortran_order else "C",
                )
                array = cast(NDArray[np.generic], mapped)
            yield array
            self._check(stopped)
            self.check_source(catalog)
        finally:
            if mapped is not None:
                # NumPy owns this mapping; no view may escape the worker lease.
                # Close its documented base object after copying prepared slices.
                import mmap

                base = mapped.base
                if isinstance(base, mmap.mmap):
                    base.close()
            if entry is not None:
                with self._lock:
                    entry.leases -= 1
                    self._trim()
                    self._cleanup()

    def _trim(self) -> None:
        size = sum(entry.size for entry in self._entries.values())
        for key, entry in tuple(self._entries.items()):
            if not entry.leases and (size > self.limit or self.stop.is_set()):
                entry.path.unlink(missing_ok=True)
                size -= entry.size
                self._entries.pop(key)
                self._stored_bytes -= entry.size

    def _cleanup(self) -> None:
        if (
            self.stop.is_set()
            and not self._preparing
            and not any(e.leases for e in self._entries.values())
        ):
            self._entries.clear()
            self._stored_bytes = 0
            if self._temporary is not None:
                self._temporary.cleanup()
                self._temporary = None

    def close(self) -> None:
        self.abandon()
        with self._lock:
            self._trim()
            self._cleanup()

    def trim(self) -> None:
        with self._lock:
            self._trim()
