from pathlib import Path

import polars as pl
import pytest

from datelier.core import ColumnRole, Dataset, SourceReference
from datelier.inspection.profiles import prepare_profiles
from datelier.pipeline import Comparison, Filter, Pipeline, SetColumnRole, Sort


def dataset(values: pl.Series) -> Dataset:
    return Dataset.from_source(
        pl.DataFrame(
            [values.rename("first"), pl.Series("feature", range(len(values)))]
        ),
        SourceReference(Path("unused.csv"), 0, 0),
    )


@pytest.mark.parametrize(
    ("values", "role"),
    [
        (pl.Series([1, 2]), ColumnRole.IDENTIFIER),
        (pl.Series(["a", "b"]), ColumnRole.IDENTIFIER),
        (pl.Series([1, 1]), ColumnRole.NUMERIC),
        (pl.Series([1, None]), ColumnRole.NUMERIC),
        (pl.Series([], dtype=pl.Int64), ColumnRole.NUMERIC),
        (pl.Series([1.0, 2.0]), ColumnRole.NUMERIC),
        (
            pl.Series(["one complete sentence", "another complete sentence"]),
            ColumnRole.TEXT,
        ),
        (pl.Series(["a.PNG", "sub/b.jpg"]), ColumnRole.IMAGE),
        (pl.Series(["a.wav", "b.mp3"]), ColumnRole.AUDIO),
        (pl.Series(["a.txt", "b.md"]), ColumnRole.EXTERNAL_TEXT),
        (pl.Series(["./a.bin", "/tmp/b.bin"]), ColumnRole.PATH),
        (pl.Series(["sub/a.bin", "other/b.bin"]), ColumnRole.PATH),
    ],
)
def test_import_interpretation_priority(values: pl.Series, role: ColumnRole) -> None:
    source = dataset(values)
    assert source.role("first").role == role
    assert source.table.get_column("first").equals(values.rename("first"))
    assert source.role("first").reason


def test_filter_does_not_reinterpret_first_source_column() -> None:
    source = dataset(pl.Series([1, 1, 2]))
    pipeline = Pipeline.start(source).apply(Filter("first", Comparison.EQ, 2))
    assert pipeline.current.role("first").role == ColumnRole.NUMERIC


def test_media_override_replay_does_not_resolve_or_change_cells() -> None:
    source = dataset(pl.Series(["missing.png", "another.png"]))
    pipeline = Pipeline.start(source).apply(SetColumnRole("first", ColumnRole.TEXT))
    pipeline = pipeline.apply(Sort(("feature",), True))
    assert pipeline.current.role("first").role == ColumnRole.TEXT
    assert pipeline.current.row_ids.to_list() == [1, 0]
    assert pipeline.undo().undo().current.role("first").role == ColumnRole.IMAGE
    assert pipeline.undo().redo().current.role("first").role == ColumnRole.TEXT
    assert [p.name for p in prepare_profiles(source).columns] == ["feature"]
