from pathlib import Path

import numpy as np
import polars as pl
import pytest

from datelier.core.column_roles import ColumnRole
from datelier.inspection.arrays.mapping import ArrayLayout
from datelier.io.arrays.aligned import (
    aligned_record_count,
    column_mapping,
    prepare_aligned_records,
)
from datelier.io.arrays.metadata import inspect_arrays
from datelier.io.arrays.storage import ArrayStore


def test_heatmap_members_become_columns_without_loading_grids(tmp_path: Path) -> None:
    path = tmp_path / "heatmap_record.npz"
    np.savez_compressed(
        path,
        heatmaps=np.zeros((4, 64, 96), dtype=np.float32),
        labels=np.arange(4, dtype=np.int32),
        scale=np.arange(4, dtype=np.float32),
    )
    original = path.read_bytes()
    catalog = inspect_arrays(path)
    store = ArrayStore()
    try:
        dataset, _ = prepare_aligned_records(store, catalog)
        assert dataset.table.columns == ["heatmaps", "labels", "scale"]
        assert dataset.table.height == 4
        assert dataset.table["labels"].to_list() == [0, 1, 2, 3]
        assert dataset.table.schema["labels"] == pl.Int32
        assert dataset.role("labels").role == ColumnRole.NUMERIC
        assert dataset.role("heatmaps").role == ColumnRole.IMAGE
        assert store.extractions == 2  # Only scalar columns, never heatmap grids.
        mapping = column_mapping(catalog, "heatmaps")
        assert mapping and mapping.layout == ArrayLayout.HEATMAP
        assert mapping.slice_settings(catalog, 3).fixed == (3, 0, 0)
        assert dataset.row_ids.to_list() == [0, 1, 2, 3]
        assert path.read_bytes() == original
    finally:
        store.close()


@pytest.mark.parametrize("other", [np.arange(3), np.array(3), np.array([{}] * 4)])
def test_mismatch_scalar_or_unsafe_member_keeps_metadata(
    tmp_path: Path,
    other: np.ndarray,
) -> None:
    path = tmp_path / "fallback.npz"
    np.savez(path, values=np.arange(4), other=other)
    assert aligned_record_count(inspect_arrays(path)) is None


def test_empty_aligned_arrays_and_reserved_names_preserve_columns(
    tmp_path: Path,
) -> None:
    path = tmp_path / "empty.npz"
    np.savez(path, record_index=np.zeros(0, dtype=">i8"), image=np.zeros((0, 2, 3)))
    store = ArrayStore()
    try:
        dataset, _ = prepare_aligned_records(store, inspect_arrays(path))
        assert dataset.table.shape == (0, 2)
        assert dataset.table.columns == ["record_index", "image"]
        assert dataset.table.schema["record_index"] == pl.Int64
    finally:
        store.close()
