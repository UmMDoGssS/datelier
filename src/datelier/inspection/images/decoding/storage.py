"""Worker-owned decoded files with mapped leases and bounded disk retention."""

from collections import OrderedDict
from collections.abc import Callable, Generator
from concurrent.futures import CancelledError
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from tempfile import NamedTemporaryFile, TemporaryDirectory
from threading import Event, RLock
from typing import cast

import numpy as np
from numpy.typing import NDArray
from PIL import Image, TiffImagePlugin

from datelier.inspection.images.decoding.sources import check_asset, image_mode
from datelier.inspection.images.geometry import orient_array
from datelier.inspection.references import AssetIdentity


@dataclass
class DecodedFile:
    path: Path
    size: int
    leases: int = 0


class ImageStore:
    """Cache limits bound retained data; oversized files remain usable while leased.

    Pillow decoding transiently allocates the decoded source in a worker. Once
    saved, original pixels are mapped read-only and only visible windows copied.
    GPU upload never depends on a source-sized texture. Close defers directory
    removal until all active decoders and leases release it.
    """

    def __init__(self, *, retained_bytes: int = 256 * 1024 * 1024) -> None:
        if retained_bytes < 0:
            raise ValueError("Image retention bytes must be nonnegative")
        self.limit = retained_bytes
        self.stop = Event()
        self._lock = RLock()
        self._temporary: TemporaryDirectory[str] | None = None
        self._entries: OrderedDict[AssetIdentity, DecodedFile] = OrderedDict()
        self._preparing = 0
        self.decodes = 0

    @property
    def stored_bytes(self) -> int:
        with self._lock:
            return sum(entry.size for entry in self._entries.values())

    @property
    def temporary_path(self) -> Path | None:
        with self._lock:
            return Path(self._temporary.name) if self._temporary else None

    def _check(self, stopped: Callable[[], bool] | None) -> None:
        if self.stop.is_set() or stopped is not None and stopped():
            raise CancelledError("Image preparation abandoned")

    def _decode(
        self, asset: AssetIdentity, stopped: Callable[[], bool] | None
    ) -> DecodedFile:
        with self._lock:
            self._check(stopped)
            if self._temporary is None:
                self._temporary = TemporaryDirectory(prefix="datelier-images-")
            directory = self._temporary.name
        path: Path | None = None
        try:
            check_asset(asset)
            with Image.open(asset.path) as image:
                mode, _, _ = image_mode(image.mode)
                orientation = (
                    int(Image.Image.getexif(image).get(274, 1))
                    if isinstance(image, TiffImagePlugin.TiffImageFile)
                    else 1
                )
                image.load()
                self._check(stopped)
                pixels = image.convert(mode) if image.mode != mode else image
                raw = np.asarray(pixels)
                if orientation != 1:
                    # TIFF decoders transpose during load. Restore its source
                    # grid so every adapter uses the same geometry contract.
                    raw = orient_array(raw, {6: 8, 8: 6}.get(orientation, orientation))
                with NamedTemporaryFile(
                    dir=directory, suffix=".npy", delete=False
                ) as stream:
                    path = Path(stream.name)
                    np.save(stream, raw, allow_pickle=False)
            self._check(stopped)
            check_asset(asset)
            self.decodes += 1
            return DecodedFile(path, path.stat().st_size)
        except BaseException:
            if path is not None:
                path.unlink(missing_ok=True)
            raise

    @contextmanager
    def open_file(
        self, asset: AssetIdentity, stopped: Callable[[], bool] | None = None
    ) -> Generator[NDArray[np.generic]]:
        self._check(stopped)
        check_asset(asset)
        with self._lock:
            entry = self._entries.get(asset)
            if entry is not None:
                entry.leases += 1
                self._entries.move_to_end(asset)
            else:
                self._preparing += 1
        if entry is None:
            try:
                prepared = self._decode(asset, stopped)
                with self._lock:
                    if self.stop.is_set():
                        prepared.path.unlink(missing_ok=True)
                        raise CancelledError("Image store is closed")
                    existing = self._entries.get(asset)
                    if existing is not None:
                        prepared.path.unlink()
                        entry = existing
                    else:
                        entry = prepared
                        self._entries[asset] = entry
                    entry.leases += 1
            finally:
                with self._lock:
                    self._preparing -= 1
                    self._cleanup()
        mapped: np.memmap | None = None
        try:
            self._check(stopped)
            mapped = cast(
                np.memmap, np.load(entry.path, mmap_mode="r", allow_pickle=False)
            )
            yield cast(NDArray[np.generic], mapped)
            self._check(stopped)
            check_asset(asset)
        finally:
            if mapped is not None:
                # NumPy has no public memmap close; release the owned mapping
                # before deleting an evicted file, as in the array store.
                backing = getattr(mapped, "_mmap", None)
                if backing is not None:
                    backing.close()
            with self._lock:
                entry.leases -= 1
                self._evict()
                self._cleanup()

    def _evict(self) -> None:
        retained = sum(entry.size for entry in self._entries.values())
        for key, entry in tuple(self._entries.items()):
            if retained <= self.limit and not self.stop.is_set():
                break
            if not entry.leases:
                entry.path.unlink(missing_ok=True)
                del self._entries[key]
                retained -= entry.size

    def _cleanup(self) -> None:
        if self.stop.is_set() and not self._preparing and not self._entries:
            if self._temporary is not None:
                self._temporary.cleanup()
                self._temporary = None

    def abandon(self) -> None:
        self.stop.set()

    def trim(self) -> None:
        with self._lock:
            self._evict()

    def cleanup(self) -> None:
        self.abandon()
        with self._lock:
            self._evict()
            self._cleanup()
