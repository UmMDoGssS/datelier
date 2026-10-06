from concurrent.futures import CancelledError, ThreadPoolExecutor
from pathlib import Path
from threading import Event
from time import perf_counter
from zipfile import ZipExtFile

import numpy as np
import pytest

from datelier.io.arrays.metadata import inspect_arrays
from datelier.io.arrays.storage import ArrayStore


@pytest.mark.parametrize("compressed", [False, True])
def test_only_selected_member_extracted_and_reused(
    tmp_path: Path, compressed: bool
) -> None:
    path = tmp_path / "data.npz"
    first = np.arange(24, dtype=">f8").reshape((2, 3, 4), order="F")
    second = np.zeros((1000, 1000), dtype=np.int16)
    (np.savez_compressed if compressed else np.savez)(path, first=first, second=second)
    original = path.read_bytes()
    catalog = inspect_arrays(path)
    store = ArrayStore(directory=tmp_path)
    try:
        assert store.temporary_path is None and store.extractions == 0
        with store.open_member(catalog, "first") as array:
            assert array.dtype == first.dtype and not array.flags.writeable
            np.testing.assert_array_equal(array[1, :, 2].copy(), first[1, :, 2])
            with pytest.raises(ValueError):
                array[0, 0, 0] = 9
        assert store.extractions == 1
        assert store.stored_bytes == catalog.member("first").container_bytes
        temporary = store.temporary_path
        assert temporary and len(list(temporary.iterdir())) == 1
        with store.open_member(catalog, "first") as array:
            np.testing.assert_array_equal(array.copy(), first)
        assert store.extractions == 1
        assert path.read_bytes() == original
    finally:
        temporary = store.temporary_path
        store.close()
        assert temporary is not None and not temporary.exists()
        assert store.stored_bytes == 0


@pytest.mark.parametrize(
    "value",
    [
        np.array(7, dtype=">i8"),
        np.zeros((0, 3)),
        np.array(["café", "line"]),
        np.array([(3, "hi")], dtype=[("tên", ">i8"), ("text", "U2")]),
    ],
)
def test_standalone_mapping_preserves_values_and_dtype_without_temp(
    tmp_path: Path, value: np.ndarray
) -> None:
    path = tmp_path / "array.npy"
    np.save(path, value, allow_pickle=False)
    catalog = inspect_arrays(path)
    store = ArrayStore()
    try:
        with store.open_member(catalog, "$") as array:
            np.testing.assert_array_equal(array.copy(), value)
            assert array.dtype == value.dtype
        assert store.temporary_path is None and store.extractions == 0
    finally:
        store.close()


def test_eviction_and_oversized_members_do_not_remove_capability(
    tmp_path: Path,
) -> None:
    path = tmp_path / "data.npz"
    np.savez_compressed(path, a=np.arange(5), b=np.arange(5), large=np.arange(1000))
    catalog = inspect_arrays(path)
    store = ArrayStore(retained_bytes=200, directory=tmp_path)
    try:
        for name in ("a", "b", "a"):
            with store.open_member(catalog, name) as array:
                np.testing.assert_array_equal(array.copy(), np.arange(5))
            assert store.stored_bytes <= 200
        assert store.extractions == 3
        with store.open_member(catalog, "large") as array:
            assert array[-1] == 999
            assert store.stored_bytes > store.limit
        assert store.stored_bytes == 0
    finally:
        temporary = store.temporary_path
        store.close()
        assert temporary and not temporary.exists()


def test_object_payload_rejected_without_pickle_and_changed_source_rejected(
    tmp_path: Path,
) -> None:
    path = tmp_path / "objects.npz"
    np.savez(path, unsafe=np.array([{"x": 1}], dtype=object))
    catalog = inspect_arrays(path)
    store = ArrayStore(directory=tmp_path)
    try:
        with pytest.raises(ValueError, match="pickle"):
            with store.open_member(catalog, "unsafe"):
                pass
        assert store.temporary_path is None
        path.write_bytes(path.read_bytes() + b" ")
        with pytest.raises(ValueError, match="changed"):
            with store.open_member(catalog, "unsafe"):
                pass
    finally:
        store.close()


def test_disk_failure_is_retryable_and_removes_partial_state(tmp_path: Path) -> None:
    path = tmp_path / "data.npz"
    np.savez(path, a=np.arange(5))
    catalog = inspect_arrays(path)
    directory = tmp_path / "missing"
    store = ArrayStore(directory=directory)
    try:
        with pytest.raises(OSError):
            with store.open_member(catalog, "a"):
                pass
        assert store.stored_bytes == 0
        directory.mkdir()
        with store.open_member(catalog, "a") as array:
            np.testing.assert_array_equal(array.copy(), np.arange(5))
        assert store.extractions == 1
    finally:
        store.close()
        assert list(directory.iterdir()) == []


def test_abandoned_preparation_and_live_lease_cleanup(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import datelier.io.arrays.storage as storage

    path = tmp_path / "data.npz"
    np.savez_compressed(path, a=np.arange(100_000))
    catalog = inspect_arrays(path)
    store = ArrayStore(directory=tmp_path)
    started, release = Event(), Event()
    original = ZipExtFile.read
    monkeypatch.setattr(storage, "CHUNK_BYTES", 256)

    def slow(self: ZipExtFile, n: int | None = -1) -> bytes:
        result = original(self, n)
        if n == 256:
            started.set()
            assert release.wait(5)
        return result

    def work() -> None:
        with store.open_member(catalog, "a") as array:
            array[:2].copy()

    monkeypatch.setattr(ZipExtFile, "read", slow)
    with ThreadPoolExecutor(max_workers=1) as workers:
        future = workers.submit(work)
        assert started.wait(2)
        temporary = store.temporary_path
        assert temporary and temporary.exists()
        start = perf_counter()
        store.close()
        assert perf_counter() - start < 0.2
        release.set()
        with pytest.raises(CancelledError):
            future.result(3)
        assert not temporary.exists() and store.stored_bytes == 0
    monkeypatch.setattr(ZipExtFile, "read", original)
    store = ArrayStore(directory=tmp_path)
    with pytest.raises(CancelledError):
        with store.open_member(catalog, "a") as array:
            temporary = store.temporary_path
            assert array[9] == 9
            store.close()
            assert temporary and temporary.exists()
    assert temporary and not temporary.exists()


def test_mapped_base_is_closed_after_each_worker_lease(tmp_path: Path) -> None:
    import mmap

    path = tmp_path / "values.npy"
    np.save(path, np.arange(1000))
    catalog = inspect_arrays(path)
    store = ArrayStore()
    try:
        for _ in range(20):
            with store.open_member(catalog, "$") as array:
                base = array.base
                assert isinstance(base, mmap.mmap) and not base.closed
                assert array[100] == 100
            assert base.closed
    finally:
        store.close()
