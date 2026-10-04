from pathlib import Path

import polars as pl
import pytest

from datelier.dataset import Dataset, SourceReference
from datelier.operations import (
    Comparison,
    Filter,
    OperationFailure,
    SelectColumns,
    Sort,
)
from datelier.pipeline import Pipeline, replay


def source() -> Dataset:
    return Dataset.from_source(
        pl.DataFrame({"^v$": [3, None, 1, 1], "label": ["c", "n", "a", "b"]}),
        SourceReference(Path("source.csv"), 0, 0),
    )


def test_order_replay_identity_and_source_preservation() -> None:
    original = source()
    pipeline = Pipeline.start(original).apply(Sort(("^v$",)))
    assert pipeline.current.row_ids.to_list() == [2, 3, 0, 1]
    pipeline = pipeline.apply(Filter("^v$", Comparison.LE, 1))
    pipeline = pipeline.apply(SelectColumns(("label",)))
    assert pipeline.current.table.rows() == [("a",), ("b",)]
    assert pipeline.current.row_ids.to_list() == [2, 3]
    repeated = replay(original, pipeline.operations)
    assert repeated.table.equals(pipeline.current.table)
    assert repeated.row_ids.equals(pipeline.current.row_ids)
    assert original.table.rows() == [(3, "c"), (None, "n"), (1, "a"), (1, "b")]
    assert pipeline.current.revision.dataset_id == original.revision.dataset_id
    with pytest.raises(OperationFailure, match="Unknown column"):
        Pipeline.start(original).apply(SelectColumns(("label",))).apply(Sort(("^v$",)))


def test_undo_redo_branch_and_atomic_failure() -> None:
    start = Pipeline.start(source())
    first = start.apply(Sort(("^v$",), descending=True))
    second = first.apply(Filter("^v$", Comparison.NOT_NULL))
    undone = second.undo()
    assert undone.current.table.equals(first.current.table)
    assert undone.current.revision != first.current.revision
    assert undone.redo().current.table.equals(second.current.table)
    with pytest.raises(OperationFailure):
        undone.apply(Sort(("missing",)))
    assert undone.can_redo
    branch = undone.apply(SelectColumns(("label",)))
    assert not branch.can_redo
    restored = branch.undo().undo()
    assert restored.current.table.equals(start.current.table)
    assert restored.current.revision != start.current.revision
    with pytest.raises(OperationFailure, match="Nothing"):
        restored.undo()


@pytest.mark.parametrize("columns", [(), ("label", "label"), ("missing",)])
def test_invalid_columns(columns: tuple[str, ...]) -> None:
    with pytest.raises(OperationFailure):
        Pipeline.start(source()).apply(SelectColumns(columns))


def test_empty_filter_and_identity_name_collision() -> None:
    dataset = source()
    table = dataset.table.with_columns(pl.lit(9).alias("__datelier_identity"))
    dataset = dataset.with_rows(table, dataset.row_ids)
    sorted_data = Pipeline.start(dataset).apply(Sort(("^v$",))).current
    assert sorted_data.table["__datelier_identity"].to_list() == [9] * 4
    empty = Pipeline.start(dataset).apply(Filter("^v$", Comparison.GT, 10))
    assert empty.current.table.shape == (0, 3)
    assert empty.current.row_ids.dtype == pl.UInt64
    assert empty.undo().current.table.equals(dataset.table)


@pytest.mark.parametrize(
    "comparison,expected",
    [
        (Comparison.EQ, [2, 3]),
        (Comparison.NE, [0]),
        (Comparison.LT, []),
        (Comparison.LE, [2, 3]),
        (Comparison.GT, [0]),
        (Comparison.GE, [0, 2, 3]),
        (Comparison.IS_NULL, [1]),
        (Comparison.NOT_NULL, [0, 2, 3]),
    ],
)
def test_comparison_semantics(comparison: Comparison, expected: list[int]) -> None:
    result = Pipeline.start(source()).apply(Filter("^v$", comparison, 1))
    assert result.current.row_ids.to_list() == expected


def test_null_comparison_requires_explicit_predicate() -> None:
    with pytest.raises(OperationFailure, match="Use is null"):
        Pipeline.start(source()).apply(Filter("^v$", Comparison.EQ, None))


def test_temporal_filter_and_invalid_values() -> None:
    from datetime import date, datetime

    table = pl.DataFrame(
        {
            "date": [date(2026, 1, 1), date(2026, 1, 2)],
            "stamp": [datetime(2026, 1, 1, 12), datetime(2026, 1, 2, 12)],
        }
    )
    pipeline = Pipeline.start(Dataset.from_source(table, source().source))
    assert pipeline.apply(
        Filter("date", Comparison.EQ, "2026-01-02")
    ).current.row_ids.to_list() == [1]
    assert pipeline.apply(
        Filter("stamp", Comparison.GT, "2026-01-01T13:00:00")
    ).current.row_ids.to_list() == [1]
    with pytest.raises(OperationFailure):
        pipeline.apply(Filter("date", Comparison.EQ, "invalid"))
    assert not pipeline.history
