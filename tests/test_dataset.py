from pathlib import Path

import polars as pl
import pytest

from datelier.core.dataset import Dataset, SourceReference


def make_dataset() -> Dataset:
    return Dataset.from_source(
        pl.DataFrame({"row_id": [30, 10, 20], "value": ["c", "a", "b"]}),
        SourceReference(Path("fixture.csv"), 42, 1),
    )


def test_identity_survives_reorder_and_filter() -> None:
    source = make_dataset()
    reordered = source.with_rows(source.table[[1, 2]], source.row_ids[[1, 2]])
    assert reordered.table["row_id"].to_list() == [10, 20]
    assert reordered.row_ids.to_list() == [1, 2]
    assert reordered.revision.dataset_id == source.revision.dataset_id
    assert reordered.revision != source.revision
    assert source.table["value"].to_list() == ["c", "a", "b"]
    assert make_dataset().revision.dataset_id != source.revision.dataset_id


@pytest.mark.parametrize(
    "ids",
    [
        pl.Series([0], dtype=pl.UInt64),
        pl.Series([0, 0, 1], dtype=pl.UInt64),
        pl.Series([0, None, 1], dtype=pl.UInt64),
        pl.Series([0, 1, 3], dtype=pl.UInt64),
        pl.Series([0, 1, 2], dtype=pl.Int64),
    ],
)
def test_invalid_identity_cannot_publish_revision(ids: pl.Series) -> None:
    dataset = make_dataset()
    revision = dataset.revision
    with pytest.raises(ValueError):
        dataset.with_rows(dataset.table, ids)
    assert dataset.revision == revision
    assert dataset.row_ids.to_list() == [0, 1, 2]


def test_empty_dataset_and_public_mutation_isolation() -> None:
    dataset = make_dataset()
    exposed = dataset.table
    exposed.drop_in_place("value")
    ids = dataset.row_ids
    ids[0] = 99
    assert dataset.table.columns == ["row_id", "value"]
    assert dataset.row_ids.to_list() == [0, 1, 2]
    empty = dataset.with_rows(dataset.table.head(0), dataset.row_ids.head(0))
    assert empty.table.height == 0
    assert empty.row_ids.dtype == pl.UInt64
