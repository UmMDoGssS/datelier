from concurrent.futures import CancelledError
from pathlib import Path
from types import ModuleType

import numpy as np
import pytest

from datelier.inspection.arrays.slices import (
    MAX_SLICE_CELLS,
    SliceSettings,
    prepare_slice,
)
from datelier.inspection.checkpoints.slices import prepare_tensor_slice
from datelier.io.arrays.metadata import inspect_arrays
from datelier.io.arrays.storage import ArrayStore
from datelier.io.checkpoints.storage import CheckpointStore
from datelier.io.importing import load_file


@pytest.fixture
def torch() -> ModuleType:
    return pytest.importorskip("torch")


def test_exact_tensor_windows_preserve_axes_values_dtypes_and_cpu_storage(
    tmp_path: Path, torch: ModuleType, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "windows.pt"
    values = torch.arange(120, dtype=torch.float64).reshape(3, 4, 10)
    torch.save({"values": values, "transpose": values[0].T}, path)
    catalog = load_file(path).checkpoint_catalog
    assert catalog
    original = path.read_bytes()
    original_load = torch.load
    observed: list[object] = []

    def checked(*args: object, **kwargs: object) -> object:
        assert kwargs["map_location"] == "cpu" and kwargs["weights_only"] is True
        assert kwargs["mmap"] is True
        loaded = original_load(*args, **kwargs)
        assert loaded["values"].device.type == "cpu"
        observed.append(loaded["values"].shape)
        return loaded

    monkeypatch.setattr(torch, "load", checked)
    store = CheckpointStore()
    try:
        result = prepare_tensor_slice(
            store,
            catalog,
            SliceSettings("$['values']", (2, 0), (0, 2, 0), (3, 0), (4, 2)),
        )
        np.testing.assert_array_equal(result.view.raw, values[:2, 2, 3:7].numpy().T)
        assert result.dtype == "torch.float64" and result.view.raw.dtype == np.float64
        assert not result.view.raw.flags.writeable
        transposed = prepare_tensor_slice(
            store, catalog, SliceSettings("$['transpose']")
        )
        np.testing.assert_array_equal(transposed.view.raw, values[0].T.numpy())
        assert store.loads == 1 and len(observed) == 1
        assert path.read_bytes() == original
    finally:
        store.close()
    assert store.stored_bytes == 0


def test_bfloat16_and_float8_keep_original_bits_beside_exact_display_values(
    tmp_path: Path, torch: ModuleType
) -> None:
    path = tmp_path / "precision.pth"
    bf16 = torch.tensor(
        [[1.5, -2.25], [float("nan"), float("inf")]], dtype=torch.bfloat16
    )
    tiny = torch.tensor([0.5, -2.0, 4.0], dtype=torch.float8_e4m3fn)
    torch.save({"bf16": bf16, "tiny": tiny}, path)
    catalog = load_file(path).checkpoint_catalog
    assert catalog
    store = CheckpointStore()
    try:
        result = prepare_tensor_slice(store, catalog, SliceSettings("$['bf16']"))
        np.testing.assert_array_equal(result.view.raw, bf16.float().numpy())
        assert result.storage and result.view.raw.dtype == np.float32
        np.testing.assert_array_equal(
            result.storage.raw, bf16.view(torch.uint16).numpy()
        )
        assert result.storage.raw.dtype == np.uint16 and result.view.nonfinite == 2
        assert "exactly as Float32" in result.view.diagnostic
        tiny_result = prepare_tensor_slice(store, catalog, SliceSettings("$['tiny']"))
        np.testing.assert_array_equal(tiny_result.view.raw, tiny.float().numpy())
        assert tiny_result.storage
        np.testing.assert_array_equal(
            tiny_result.storage.raw, tiny.view(torch.uint8).numpy()
        )
    finally:
        store.close()


def test_complex_integer_scalar_empty_and_bounded_tensor_windows(
    tmp_path: Path, torch: ModuleType
) -> None:
    path = tmp_path / "types.ckpt"
    torch.save(
        {
            "complex": torch.tensor([1 + 2j, 3 - 4j], dtype=torch.complex128),
            "integer": torch.tensor([2**63 + 1, 2**64 - 1], dtype=torch.uint64),
            "scalar": torch.tensor(7),
            "empty": torch.empty((0, 3)),
            "large": torch.zeros((300, 400)),
        },
        path,
    )
    catalog = load_file(path).checkpoint_catalog
    assert catalog
    store = CheckpointStore()
    try:
        value = prepare_tensor_slice(
            store, catalog, SliceSettings("$['complex']", component="Imaginary")
        )
        assert value.view.numeric is not None and value.view.numeric.tolist() == [2, -4]
        assert value.view.raw.dtype == np.complex128
        integer = prepare_tensor_slice(store, catalog, SliceSettings("$['integer']"))
        assert integer.view.raw.tolist() == [2**63 + 1, 2**64 - 1]
        scalar = prepare_tensor_slice(store, catalog, SliceSettings("$['scalar']"))
        assert scalar.view.raw.shape == () and int(scalar.view.raw) == 7
        empty = prepare_tensor_slice(
            store, catalog, SliceSettings("$['empty']", scalar=True)
        )
        assert empty.view.raw.size == 0 and not empty.view.cells
        large = prepare_tensor_slice(
            store, catalog, SliceSettings("$['large']", counts=(4096, 4096))
        )
        assert large.view.raw.size <= MAX_SLICE_CELLS and large.view.limited
    finally:
        store.close()


def test_legacy_retention_source_changes_and_abandonment_remain_explicit(
    tmp_path: Path, torch: ModuleType
) -> None:
    path = tmp_path / "legacy.pth"
    torch.save(
        {"weight": torch.arange(100)}, path, _use_new_zipfile_serialization=False
    )
    catalog = load_file(path).checkpoint_catalog
    assert catalog and not catalog.mapped
    store = CheckpointStore(retained_bytes=1)
    result = prepare_tensor_slice(
        store, catalog, SliceSettings("$['weight']", counts=(3,))
    )
    assert result.view.raw.tolist() == [0, 1, 2] and store.stored_bytes == 0
    assert store.loads == 1
    store.abandon()
    with pytest.raises(CancelledError, match="abandoned"):
        prepare_tensor_slice(store, catalog, SliceSettings("$['weight']"))
    store.close()
    other = CheckpointStore()
    try:
        path.write_bytes(b"changed")
        with pytest.raises(ValueError, match="source changed"):
            prepare_tensor_slice(other, catalog, SliceSettings("$['weight']"))
    finally:
        other.close()


def test_fixed_empty_numpy_window_never_shows_uninitialized_scalar(
    tmp_path: Path,
) -> None:
    path = tmp_path / "empty.npy"
    np.save(path, np.empty((0, 3), dtype=np.float32))
    catalog = inspect_arrays(path)
    store = ArrayStore()
    try:
        result = prepare_slice(store, catalog, SliceSettings(scalar=True))
        assert result.raw.size == 0 and result.cells == ()
    finally:
        store.close()
