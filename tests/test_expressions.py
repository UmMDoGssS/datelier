from pathlib import Path

import polars as pl
import pytest

from datelier.core import Dataset, SourceReference
from datelier.pipeline import (
    Comparison,
    Filter,
    OperationFailure,
    Pipeline,
    Sort,
    replay,
)
from datelier.pipeline.transforms import DerivedColumn


def start() -> Pipeline:
    return Pipeline.start(
        Dataset.from_source(
            pl.DataFrame({"^v$": [3, None, 1], "text": ["ÄBC", "xyz", ""]}),
            SourceReference(Path("fixture"), 0, 0),
        )
    )


def test_derived_arithmetic_nulls_boolean_strings_and_replay() -> None:
    pipeline = start().apply(Sort(("^v$",))).apply(Filter("^v$", Comparison.NOT_NULL))
    for name, expression, expected in (
        ("score", 'fill_null(col("^v$"), 0) * 2 + 1', [3, 7]),
        ("eligible", '1 <= col("^v$") < 3 and not is_null(col("text"))', [True, False]),
        (
            "label",
            'where(col("^v$") > 1, lower(col("text")), "small")',
            ["small", "äbc"],
        ),
        ("length", 'length(col("text"))', [0, 3]),
        ("root", 'sqrt(abs(-col("^v$")))', [1.0, 3**0.5]),
        ("constant", "5", [5, 5]),
    ):
        pipeline = pipeline.apply(DerivedColumn(name, expression))
        assert pipeline.current.table[name].to_list() == expected
        assert pipeline.current.row_ids.to_list() == [2, 0]
    repeated = replay(pipeline.source, pipeline.operations)
    assert repeated.table.equals(pipeline.current.table)
    assert repeated.row_ids.equals(pipeline.current.row_ids)
    assert pipeline.undo().redo().current.table.equals(pipeline.current.table)


def test_explicit_replacement_null_and_empty_results() -> None:
    pipeline = start()
    with pytest.raises(OperationFailure, match="exists"):
        pipeline.apply(DerivedColumn("text", 'upper(col("text"))'))
    result = pipeline.apply(DerivedColumn("text", 'upper(col("text"))', replace=True))
    assert result.current.table["text"].to_list() == ["ÄBC", "XYZ", ""]
    result = result.apply(DerivedColumn("^new$", 'col("^v$") / 2'))
    assert result.current.table["^new$"].to_list() == [1.5, None, 0.5]
    empty = pipeline.apply(Filter("^v$", Comparison.GT, 99)).apply(
        DerivedColumn("constant", "1")
    )
    assert empty.current.table.shape == (0, 3)


@pytest.mark.parametrize(
    "expression",
    [
        '__import__("os").system("true")',
        'open("/tmp/forbidden", "w")',
        'col("text").str',
        'col("text")[0]',
        "(lambda: 1)()",
        "[x for x in [1]]",
        'sum(col("^v$"))',
        "col(name)",
        'col("missing")',
        'col(name="text")',
        'col("^v$") ** 100',
        'col("text") is None',
        "1e999",
        "999999999999999999999999",
        "1 +",
        "",
        "x",
        "sqrt(1, 2)",
        "where(True, 1)",
        '"x" * 999999999999999999999',
    ],
)
def test_unsupported_syntax_never_changes_history(
    expression: str, tmp_path: Path
) -> None:
    pipeline = start()
    with pytest.raises(OperationFailure):
        pipeline.apply(DerivedColumn("new", expression))
    assert not pipeline.history
    assert not (tmp_path / "forbidden").exists()


def test_code_execution_rejection_has_no_side_effects(tmp_path: Path) -> None:
    marker = tmp_path / "marker"
    expression = f'__import__("pathlib").Path({str(marker)!r}).write_text("executed")'
    with pytest.raises(OperationFailure):
        start().apply(DerivedColumn("bad", expression))
    assert not marker.exists()


@pytest.mark.parametrize(
    "expression", ["+" * 4100 + "1", " + ".join(["1"] * 150), '"' + "x" * 1025 + '"']
)
def test_expression_resource_bounds(expression: str) -> None:
    with pytest.raises(OperationFailure):
        start().apply(DerivedColumn("new", expression))
