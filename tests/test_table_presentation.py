from dataclasses import replace
from pathlib import Path

import polars as pl
import pytest

from datelier.core.dataset import Dataset, SourceReference
from datelier.inspection.presentation import NumericScale, TablePresentation, cell_style
from datelier.inspection.table import Inspection, prepare_inspection
from datelier.io.types import CsvOptions, ImportResult
from datelier.pipeline.history import Pipeline
from datelier.pipeline.operations import Comparison, Filter, Sort


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


def test_category_palette_is_stable_after_sort_filter_and_undo() -> None:
    data = inspect(pl.DataFrame({"id": [1, 2, 3], "category": ["a", "b", "a"]}))
    original = data.first_page.cells[0][1]
    pipeline = (
        Pipeline.start(data.dataset)
        .apply(Sort(("id",), True))
        .apply(Filter("category", Comparison.EQ, "a"))
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
