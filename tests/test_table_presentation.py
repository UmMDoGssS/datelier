from dataclasses import replace
from pathlib import Path

import polars as pl
import pytest

from datelier.core import Dataset, SourceReference
from datelier.inspection.presentation import NumericScale, TablePresentation, cell_style
from datelier.inspection.table import Inspection, prepare_inspection
from datelier.io.types import CsvOptions, ImportResult
from datelier.pipeline import Comparison, Filter, Pipeline, Sort


def inspect(table: pl.DataFrame) -> Inspection:
    data = Dataset.from_source(table, SourceReference(Path("unused"), 0, 0))
    return prepare_inspection(ImportResult(data, CsvOptions(), ()))


def test_typed_null_differs_from_literal_null_and_nonfinite() -> None:
    data = inspect(
        pl.DataFrame(
            {
                "x": [None, 1.0, float("nan"), float("inf")],
                "category": [None, "NULL", "a", "a"],
            }
        )
    )
    cells = data.first_page.cells
    assert data.first_page.rows[0][1] == data.first_page.rows[1][1] == "NULL"
    assert cells[0][1].is_null and not cells[1][1].is_null
    assert cell_style(cells[0][1], None, TablePresentation()).marker == "(null)"
    null_style = cell_style(cells[0][1], None, TablePresentation())
    assert null_style.rgba == (1, 1, 1) and null_style.foreground == (0, 0, 0)
    assert null_style.bold and null_style.opaque
    assert not cell_style(cells[1][1], None, TablePresentation()).marker
    assert cells[2][0].nonfinite and cells[3][0].nonfinite
    assert cell_style(cells[2][0], data.bounds[0], TablePresentation()).marker == "!"


def test_percentile_linear_custom_constant_and_overflow_ranges() -> None:
    data = inspect(pl.DataFrame({"x": [float(i) for i in range(101)]}))
    bounds = data.bounds[0]
    assert (
        bounds.minimum,
        bounds.maximum,
        bounds.percentile_low,
        bounds.percentile_high,
    ) == (0, 100, 2, 98)
    first, last = data.first_page.cells[0][0], data.first_page.cells[99][0]
    settings = TablePresentation()
    assert cell_style(first, bounds, settings).marker == "<"
    assert cell_style(last, bounds, settings).marker == ">"
    assert not cell_style(
        first, bounds, replace(settings, scale=NumericScale.LINEAR)
    ).marker
    custom = replace(settings, scale=NumericScale.CUSTOM, minimum=10, maximum=20)
    assert cell_style(first, bounds, custom).marker == "<"
    tiny = replace(settings, scale=NumericScale.CUSTOM, minimum=1e-308, maximum=2e-308)
    huge_cell = inspect(pl.DataFrame({"x": [1e308]})).first_page.cells[0][0]
    assert (
        cell_style(huge_cell, bounds, tiny).rgba
        == cell_style(last, bounds, settings).rgba
    )
    constant = inspect(pl.DataFrame({"x": [5.0, 5.0]}))
    assert (
        cell_style(constant.first_page.cells[0][0], constant.bounds[0], settings).marker
        == "="
    )
    huge = inspect(pl.DataFrame({"x": [-1e308, 0.0, 1e308]}))
    for row in huge.first_page.cells:
        style = cell_style(row[0], huge.bounds[0], settings)
        assert style.rgba and all(0 <= c <= 1 for c in style.rgba)
    with pytest.raises(ValueError):
        replace(settings, maximum=0).validate()


def test_nontext_category_palette_is_stable_after_sort_filter_and_undo() -> None:
    data = inspect(pl.DataFrame({"id": [1, 2, 3], "category": [True, False, True]}))
    original = data.first_page.cells[0][1]
    pipeline = (
        Pipeline.start(data.dataset)
        .apply(Sort(("id",), True))
        .apply(Filter("category", Comparison.EQ, True))
    )
    edited = prepare_inspection(replace(data.imported, dataset=pipeline.current))
    assert edited.first_page.row_ids == (2, 0)
    assert all(row[1].category == original.category for row in edited.first_page.cells)
    assert (
        cell_style(original, None, TablePresentation()).rgba
        == cell_style(edited.first_page.cells[0][1], None, TablePresentation()).rgba
    )
    restored = prepare_inspection(
        replace(data.imported, dataset=pipeline.undo().undo().current)
    )
    assert restored.first_page.cells == data.first_page.cells
    assert cell_style(original, None, TablePresentation(enabled=False)).rgba is None


def test_text_length_uses_original_unicode_length_and_crest() -> None:
    data = inspect(
        pl.DataFrame({"id": [1, 2, 3, 4], "text": ["", "中文🙂", "x" * 500, None]})
    )
    bounds = next(b for b in data.bounds if b.column == "text")
    assert bounds.minimum == 0 and bounds.maximum == 500
    cells = [row[1] for row in data.first_page.cells]
    assert [cell.text_length for cell in cells] == [0, 3, 500, None]
    assert len(data.first_page.rows[2][1]) == 257
    settings = TablePresentation(scale=NumericScale.LINEAR)
    low, high = [cell_style(cells[i], bounds, settings) for i in (0, 2)]
    assert low.rgba == (0.6468274, 0.80289262, 0.56592265)
    assert high.rgba == pytest.approx((0.17363177, 0.19076859, 0.44549087))
    assert cell_style(cells[3], bounds, settings).opaque
    custom = replace(settings, scale=NumericScale.CUSTOM, minimum=1, maximum=10)
    assert cell_style(cells[2], bounds, custom).marker == ">"


@pytest.mark.parametrize(
    "dtype", [pl.String, pl.Categorical, pl.Enum(["a", "alphabet"])]
)
def test_repeated_and_categorical_strings_use_crest_lengths(dtype: pl.DataType) -> None:
    data = inspect(
        pl.DataFrame(
            {"id": [1, 2, 3], "label": pl.Series(["a", "alphabet", "a"], dtype=dtype)}
        )
    )
    bounds = next(b for b in data.bounds if b.column == "label")
    assert (bounds.minimum, bounds.maximum) == (1, 8)
    assert [row[1].text_length for row in data.first_page.cells] == [1, 8, 1]
    settings = TablePresentation(scale=NumericScale.LINEAR)
    assert cell_style(data.first_page.cells[0][1], bounds, settings).rgba == (
        0.6468274,
        0.80289262,
        0.56592265,
    )
    assert cell_style(
        data.first_page.cells[1][1], bounds, settings
    ).rgba == pytest.approx((0.17363177, 0.19076859, 0.44549087))
