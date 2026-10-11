from pathlib import Path

import numpy as np
import pytest

from datelier.inspection.arrays.slices import SliceSettings, prepare_slice
from datelier.io.arrays import ArrayStore
from datelier.io.arrays.metadata import inspect_arrays


def test_higher_dimensional_axis_order_and_fixed_indices_preserve_exact_values(
    tmp_path: Path,
) -> None:
    path = tmp_path / "cube.npy"
    values = np.arange(4 * 3 * 5, dtype=">i8").reshape(4, 3, 5)
    np.save(path, values)
    store = ArrayStore()
    try:
        result = prepare_slice(
            store,
            inspect_arrays(path),
            SliceSettings(axes=(2, 0), fixed=(0, 1, 0), starts=(1, 2), counts=(3, 2)),
        )
        expected = values[2:4, 1, 1:4].T
        np.testing.assert_array_equal(result.raw, expected)
        assert result.raw.dtype == values.dtype and result.axes == (2, 0)
        assert result.cells == tuple(tuple(str(v) for v in row) for row in expected)
        assert not result.raw.flags.writeable
        assert result.limited and result.starts == (1, 2)
        # A different view uses the same source coordinates, not display positions.
        vector = prepare_slice(
            store, inspect_arrays(path), SliceSettings(axes=(1,), fixed=(3, 0, 4))
        )
        np.testing.assert_array_equal(vector.raw, values[3, :, 4])
    finally:
        store.close()


@pytest.mark.parametrize(
    "values",
    [np.array(7), np.zeros((0, 4)), np.zeros((0, 5, 4)), np.array(["café", "last"])],
)
def test_scalar_empty_and_string_values_have_prepared_raw_cells(
    tmp_path: Path, values: np.ndarray
) -> None:
    path = tmp_path / "values.npy"
    np.save(path, values)
    store = ArrayStore()
    try:
        result = prepare_slice(store, inspect_arrays(path), SliceSettings())
        assert result.raw.dtype == values.dtype
        if values.shape == ():
            assert result.cells == (("7",),)
        elif values.size == 0:
            assert result.cells == () and result.raw.size == 0
        else:
            assert result.cells == (("café",), ("last",)) and result.numeric is None
            assert "raw values" in result.diagnostic
    finally:
        store.close()


def test_numeric_colors_preserve_nonfinite_large_magnitudes_and_constants(
    tmp_path: Path,
) -> None:
    path = tmp_path / "values.npz"
    np.savez_compressed(
        path,
        extremes=np.array([[-1e308, 0, 1e308], [np.nan, np.inf, -np.inf]]),
        flat=np.ones((2, 2)),
        complex=np.array([1 + 2j, 3 + 4j]),
    )
    store = ArrayStore()
    try:
        catalog = inspect_arrays(path)
        result = prepare_slice(store, catalog, SliceSettings("extremes"))
        assert result.colors is not None and result.nonfinite == 3
        np.testing.assert_array_equal(result.colors[0], [0, 0.5, 1])
        assert np.isnan(result.colors[1]).all()
        assert result.finite_range == (-1e308, 1e308)
        flat = prepare_slice(store, catalog, SliceSettings("flat"))
        np.testing.assert_array_equal(flat.colors, np.full((2, 2), 0.5))
        complex = prepare_slice(
            store, catalog, SliceSettings("complex", component="Imaginary")
        )
        np.testing.assert_array_equal(complex.numeric, [2, 4])
        np.testing.assert_array_equal(complex.raw, [1 + 2j, 3 + 4j])
    finally:
        store.close()


def test_structured_field_plot_keeps_original_records(tmp_path: Path) -> None:
    path = tmp_path / "records.npy"
    values = np.array(
        [(3.5, "café"), (7.5, "last")], dtype=[("value", ">f8"), ("label", "U4")]
    )
    np.save(path, values)
    store = ArrayStore()
    try:
        result = prepare_slice(
            store, inspect_arrays(path), SliceSettings(field="value")
        )
        np.testing.assert_array_equal(result.raw, values)
        np.testing.assert_array_equal(result.numeric, [3.5, 7.5])
        assert "café" in result.cells[0][0]
    finally:
        store.close()


def test_large_windows_are_exact_limited_slices_with_no_source_edits(
    tmp_path: Path,
) -> None:
    path = tmp_path / "matrix.npy"
    values = np.arange(400 * 400).reshape(400, 400)
    np.save(path, values)
    original = path.read_bytes()
    store = ArrayStore()
    try:
        result = prepare_slice(
            store,
            inspect_arrays(path),
            SliceSettings(starts=(12, 15), counts=(300, 300)),
        )
        assert result.raw.size <= 16_384 and result.limited
        rows, columns = result.raw.shape
        np.testing.assert_array_equal(
            result.raw, values[12 : 12 + rows, 15 : 15 + columns]
        )
        assert path.read_bytes() == original
    finally:
        store.close()


@pytest.mark.parametrize(
    "settings",
    [
        SliceSettings(axes=(3,)),
        SliceSettings(axes=(1, 1)),
        SliceSettings(axes=(1,), fixed=(0,)),
        SliceSettings(axes=(1,), fixed=(99, 0)),
        SliceSettings(starts=(99, 0)),
        SliceSettings(counts=(0, 2)),
        SliceSettings(field="absent"),
    ],
)
def test_invalid_windows_do_not_alter_source_or_cache(
    tmp_path: Path, settings: SliceSettings
) -> None:
    path = tmp_path / "matrix.npy"
    np.save(path, np.arange(6).reshape(2, 3))
    original = path.read_bytes()
    store = ArrayStore()
    try:
        with pytest.raises(ValueError):
            prepare_slice(store, inspect_arrays(path), settings)
        assert path.read_bytes() == original and store.stored_bytes == 0
    finally:
        store.close()
