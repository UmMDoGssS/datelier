from dataclasses import replace
from pathlib import Path

import numpy as np
import polars as pl
import pytest

from datelier.core.column_roles import ColumnRole
from datelier.inspection.arrays.mapping import ArrayLayout
from datelier.inspection.images.sources import image_metadata, locate_image
from datelier.inspection.references.types import ReferenceSettings
from datelier.io.arrays.aligned import (
    aligned_record_count,
    column_mapping,
    prepare_aligned_records,
)
from datelier.io.arrays.importing import load_arrays
from datelier.io.arrays.metadata import inspect_arrays
from datelier.io.arrays.storage import ArrayStore
from datelier.io.types import ArrayOptions
from datelier.pipeline.history import Pipeline
from datelier.pipeline.operations import Sort
from datelier.workspace.codec import decode_record, encode


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


def test_default_open_maps_each_sorted_image_column(tmp_path: Path) -> None:
    path = tmp_path / "records.npz"
    np.savez_compressed(
        path,
        heatmaps=np.arange(4 * 64 * 96).reshape(4, 64, 96),
        images=np.zeros((4, 32, 48, 3), dtype=np.uint8),
        labels=np.array([3, 1, 2, 0], dtype=">i4"),
        names=np.array(["a", "b", "c", "d"]),
    )
    imported = load_arrays(path)
    options, catalog = imported.options, imported.array_catalog
    assert isinstance(options, ArrayOptions) and catalog
    assert imported.dataset.table.shape == (4, 4)
    assert options.mapping is None
    assert imported.dataset.table["names"].to_list() == ["a", "b", "c", "d"]
    dataset = Pipeline.start(imported.dataset).apply(Sort(("labels",))).current
    assert dataset.row_ids.to_list() == [3, 1, 2, 0]
    for column, dimensions, layout in (
        ("heatmaps", (96, 64), ArrayLayout.HEATMAP),
        ("images", (48, 32), ArrayLayout.IMAGE),
    ):
        mapping = options.mapping_for(catalog, column)
        assert mapping and mapping.member == column and mapping.layout == layout
        locator = locate_image(
            dataset, "file", "", column, 0, ReferenceSettings(), None, catalog, mapping
        )
        assert locator.source_index == 3 and locator.origin.row_id == 3
        metadata = image_metadata(locator)
        assert (metadata.width, metadata.height) == dimensions
    assert options.mapping_for(catalog, "labels") is None
    metadata_view = load_arrays(path, replace(options, record_table=False))
    assert metadata_view.dataset.table.columns[0] == "member"


def test_mismatch_and_npy_default_to_member_metadata(tmp_path: Path) -> None:
    path = tmp_path / "mismatch.npz"
    np.savez(path, images=np.zeros((4, 2, 3)), labels=np.arange(3))
    assert load_arrays(path).dataset.table["member"].to_list() == ["images", "labels"]
    single = tmp_path / "single.npy"
    np.save(single, np.arange(4))
    assert load_arrays(single).dataset.table["member"].to_list() == ["$"]


def test_workspace_option_migration_preserves_metadata_identity() -> None:
    legacy = {
        "kind": "ArrayOptions",
        "archive": None,
        "max_header_bytes": 10_000,
        "mapping": None,
    }
    assert not decode_record(ArrayOptions, legacy).record_table
    options = ArrayOptions()
    assert decode_record(ArrayOptions, encode(options)) == options


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
