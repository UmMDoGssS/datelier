from pathlib import Path

import polars as pl
import pytest

from datelier.dataset import Dataset, SourceReference
from datelier.operations import OperationFailure, Sort
from datelier.pipeline import Pipeline, replay
from datelier.transform_types import (
    CastColumn,
    DropMissing,
    FillMissing,
    Lookup,
    TargetType,
    Unmatched,
)


def start(table: pl.DataFrame) -> Pipeline:
    return Pipeline.start(
        Dataset.from_source(table, SourceReference(Path("fixture"), 0, 0))
    )


def test_strict_and_null_casts_failure_atomicity() -> None:
    pipeline = start(pl.DataFrame({"^v$": ["1", "bad", None, "3"]}))
    with pytest.raises(OperationFailure, match="conversion"):
        pipeline.apply(CastColumn("^v$", TargetType.INT))
    assert not pipeline.history
    result = pipeline.apply(CastColumn("^v$", TargetType.INT, strict=False))
    assert result.current.table["^v$"].to_list() == [1, None, None, 3]
    assert result.current.table.schema["^v$"] == pl.Int64
    assert result.undo().current.table.equals(pipeline.current.table)
    assert replay(pipeline.source, result.operations).table.equals(result.current.table)


def test_missing_values_and_nonfinite_alignment() -> None:
    pipeline = start(
        pl.DataFrame({"^v$": [1.0, None, float("nan"), float("inf"), 2.0]})
    )
    filled = pipeline.apply(FillMissing("^v$", 0))
    assert filled.current.table["^v$"].null_count() == 0
    assert filled.current.table["^v$"].alias("value").is_nan().sum() == 1
    finite = pipeline.apply(FillMissing("^v$", 0, include_nonfinite=True))
    assert finite.current.table["^v$"].to_list() == [1, 0, 0, 0, 2]
    dropped = pipeline.apply(Sort(("^v$",))).apply(DropMissing(("^v$",), True))
    assert dropped.current.row_ids.to_list() == [0, 4]
    assert dropped.current.table["^v$"].to_list() == [1, 2]
    with pytest.raises(OperationFailure):
        pipeline.apply(FillMissing("^v$", "bad"))
    with pytest.raises(OperationFailure, match="non-null"):
        pipeline.apply(FillMissing("^v$", None))


@pytest.mark.parametrize(
    "strategy,expected",
    [(Unmatched.KEEP, [10, 2, None]), (Unmatched.NULL, [10, None, None])],
)
def test_lookup_unmatched_and_literal_names(
    strategy: Unmatched, expected: list[int | None]
) -> None:
    pipeline = start(pl.DataFrame({"^v$": [1, 2, None]}))
    mapped = pipeline.apply(Lookup("^v$", ((1, 10),), TargetType.INT, strategy))
    assert mapped.current.table["^v$"].to_list() == expected
    assert mapped.current.row_ids.to_list() == [0, 1, 2]
    assert mapped.undo().redo().current.table.equals(mapped.current.table)


def test_lookup_null_key_type_conversion_and_rejections() -> None:
    pipeline = start(pl.DataFrame({"v": [1, 2, None]}))
    recipe = Lookup(
        "v",
        ((1, "one"), (2, "two"), (None, "missing")),
        TargetType.TEXT,
        Unmatched.ERROR,
    )
    result = pipeline.apply(recipe)
    assert result.current.table["v"].to_list() == ["one", "two", "missing"]
    for operation in (
        Lookup("v", ((1, 10),), TargetType.INT, Unmatched.ERROR),
        Lookup("v", ((1, 10), ("1", 20)), TargetType.INT),
        Lookup("v", (), TargetType.INT),
        Lookup("v", ((1, "bad"),), TargetType.INT),
        Lookup("v", ((1, "one"),), TargetType.TEXT, Unmatched.KEEP),
    ):
        # Last case succeeds because unmatched integers can convert to text.
        if operation.dtype == TargetType.TEXT:
            assert pipeline.apply(operation).current.table["v"].to_list() == [
                "one",
                "2",
                None,
            ]
        else:
            with pytest.raises(OperationFailure):
                pipeline.apply(operation)
    assert not pipeline.history


@pytest.mark.parametrize(
    "dtype,values",
    [
        (TargetType.UINT, [1, 2]),
        (TargetType.DATE, ["2026-01-01", "2026-01-02"]),
        (TargetType.BOOL, [0, 1]),
    ],
)
def test_cast_types_and_empty_table(
    dtype: TargetType, values: list[int] | list[str]
) -> None:
    pipeline = start(pl.DataFrame({"v": values}))
    result = pipeline.apply(CastColumn("v", dtype))
    assert result.current.table.height == 2
    empty = start(pipeline.current.table.head(0)).apply(CastColumn("v", dtype))
    assert empty.current.table.height == 0


def test_all_null_and_multiple_column_drop() -> None:
    pipeline = start(
        pl.DataFrame(
            {"v": [None, None], "w": [1, None]}, schema={"v": pl.Int64, "w": pl.Int64}
        )
    )
    assert pipeline.apply(FillMissing("v", 5)).current.table["v"].to_list() == [5, 5]
    dropped = pipeline.apply(DropMissing(("v", "w")))
    assert dropped.current.table.shape == (0, 2)
    assert dropped.current.row_ids.to_list() == []
