from pathlib import Path

import numpy as np
import pytest

from datelier.inspection.arrays.mapping import (
    ArrayLayout,
    ArrayRecordMapping,
    SupportingArray,
    suggest_mapping,
)
from datelier.inspection.arrays.slices import prepare_slice
from datelier.io.arrays.metadata import inspect_arrays
from datelier.io.arrays.records import prepare_array_records
from datelier.io.arrays.storage import ArrayStore
from datelier.pipeline.history import Pipeline
from datelier.pipeline.operations import Sort


def test_suggestion_does_not_read_payload_and_nhwc_records_align_after_explicit_mapping(
    tmp_path: Path,
) -> None:
    path = tmp_path / "images.npz"
    images = np.arange(5 * 8 * 7 * 3, dtype=np.uint8).reshape(5, 8, 7, 3)
    labels = np.array([4, 1, 3, 0, 2])
    np.savez_compressed(path, images=images, labels=labels)
    catalog = inspect_arrays(path)
    store = ArrayStore()
    try:
        suggestion = suggest_mapping(catalog, "images")
        assert (
            suggestion.mapping.record_axis == 0 and suggestion.mapping.channel_axis == 3
        )
        assert suggestion.mapping.display_axes == (1, 2)
        assert suggestion.supporting_members == ("labels",)
        assert store.temporary_path is None
        mapping = ArrayRecordMapping(
            "images",
            0,
            ArrayLayout.IMAGE,
            (1, 2),
            3,
            supporting=(SupportingArray("labels", "label"),),
        )
        dataset, diagnostics = prepare_array_records(store, catalog, mapping)
        assert dataset.table.rows() == list(zip(range(5), labels.tolist(), strict=True))
        assert (
            store.extractions == 1
        )  # scalar labels only; image payload stays unopened
        pipeline = Pipeline.start(dataset).apply(Sort(("label",)))
        assert pipeline.current.row_ids.to_list() == [3, 1, 4, 2, 0]
        for row_id, label in zip(
            pipeline.current.row_ids.to_list(),
            pipeline.current.table["label"].to_list(),
            strict=True,
        ):
            frame = prepare_slice(
                store, catalog, mapping.slice_settings(catalog, row_id, channel=2)
            )
            np.testing.assert_array_equal(frame.raw, images[row_id, :, :, 2])
            assert label == labels[row_id]
        assert pipeline.undo().current.table.equals(dataset.table)
        assert diagnostics and path.exists()
    finally:
        store.close()


def test_nchw_alternate_record_axes_and_supporting_coordinates(tmp_path: Path) -> None:
    path = tmp_path / "layouts.npz"
    images = np.arange(4 * 3 * 6 * 7, dtype=np.float32).reshape(4, 3, 6, 7)
    supporting = np.arange(2 * 4).reshape(2, 4)
    np.savez(
        path, images=images, alternate=images.transpose(1, 2, 0, 3), support=supporting
    )
    catalog = inspect_arrays(path)
    store = ArrayStore()
    try:
        mapping = ArrayRecordMapping(
            "images",
            0,
            ArrayLayout.IMAGE,
            (2, 3),
            1,
            supporting=(SupportingArray("support", "label", 1, (1, 0)),),
        )
        dataset, _ = prepare_array_records(store, catalog, mapping)
        assert dataset.table["label"].to_list() == [4, 5, 6, 7]
        frame = prepare_slice(
            store, catalog, mapping.slice_settings(catalog, 2, channel=1)
        )
        np.testing.assert_array_equal(frame.raw, images[2, 1])
        alternate = ArrayRecordMapping("alternate", 2, ArrayLayout.IMAGE, (1, 3), 0)
        frame = prepare_slice(
            store, catalog, alternate.slice_settings(catalog, 2, channel=1)
        )
        np.testing.assert_array_equal(frame.raw, images[2, 1])
    finally:
        store.close()


def test_ambiguity_and_unequal_lengths_require_configuration_without_truncation(
    tmp_path: Path,
) -> None:
    path = tmp_path / "ambiguous.npz"
    np.savez(path, data=np.zeros((3, 8, 7, 3)), labels=np.arange(3), wrong=np.arange(2))
    catalog = inspect_arrays(path)
    suggestion = suggest_mapping(catalog, "data")
    assert suggestion.record_axes == (0, 3) and "confirm" in suggestion.reason
    mapping = ArrayRecordMapping(
        "data", supporting=(SupportingArray("wrong", "label"),)
    )
    store = ArrayStore()
    try:
        with pytest.raises(ValueError, match="without truncation"):
            prepare_array_records(store, catalog, mapping)
        assert store.temporary_path is None
    finally:
        store.close()


@pytest.mark.parametrize(
    "layout,shape,axes,channel",
    [
        (ArrayLayout.IMAGE, (3, 8, 7), (1, 2), None),
        (ArrayLayout.HEATMAP, (3, 8, 7), (1, 2), None),
        (ArrayLayout.AUDIO, (3, 128, 2), (1,), 2),
    ],
)
def test_grayscale_heatmap_and_waveform_layouts_retain_source_index(
    tmp_path: Path,
    layout: ArrayLayout,
    shape: tuple[int, ...],
    axes: tuple[int, ...],
    channel: int | None,
) -> None:
    path = tmp_path / "values.npy"
    values = np.arange(np.prod(shape), dtype=np.float32).reshape(shape)
    np.save(path, values)
    catalog = inspect_arrays(path)
    mapping = ArrayRecordMapping("$", 0, layout, axes, channel)
    store = ArrayStore()
    try:
        dataset, _ = prepare_array_records(store, catalog, mapping)
        assert dataset.row_ids.to_list() == [0, 1, 2]
        settings = mapping.slice_settings(
            catalog, 1, channel=1 if channel is not None else 0
        )
        frame = prepare_slice(store, catalog, settings)
        np.testing.assert_array_equal(
            frame.raw, values[1, :, 1] if channel else values[1]
        )
    finally:
        store.close()


def test_scalar_record_axis_and_empty_record_schema(tmp_path: Path) -> None:
    path = tmp_path / "scalar-records.npy"
    np.save(path, np.array([7, 9, 12], dtype=">i8"))
    catalog = inspect_arrays(path)
    mapping = ArrayRecordMapping("$")
    store = ArrayStore()
    try:
        frame = prepare_slice(store, catalog, mapping.slice_settings(catalog, 1))
        assert frame.raw.shape == () and frame.cells == (("9",),)
        np.save(path, np.zeros((0, 4, 5)))
        empty = inspect_arrays(path)
        mapping = ArrayRecordMapping("$", 0, ArrayLayout.HEATMAP, (1, 2))
        dataset, _ = prepare_array_records(store, empty, mapping)
        assert dataset.table.height == 0 and dataset.table.columns == ["record_index"]
    finally:
        store.close()
