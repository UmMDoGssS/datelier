"""Element means retain row identity and lazy payloads without changing values."""

from dataclasses import replace
from pathlib import Path

import numpy as np
import polars as pl
import pytest
from test_rebuild_sources import until

from datelier.application.sessions import EditorController
from datelier.core import ColumnRole, Dataset, SourceReference
from datelier.inspection.arrays import ArrayLayout, ArrayRecordMapping
from datelier.inspection.arrays.presentation import (
    array_mappings,
    prepare_array_page,
    prepare_array_record_page,
)
from datelier.inspection.presentation import (
    NumericScale,
    TablePresentation,
    cell_style,
    prepare_column_cells,
)
from datelier.inspection.records import InspectSettings
from datelier.inspection.records.prepare import prepare_record_page, prepare_records
from datelier.inspection.table import Inspection, prepare_inspection
from datelier.io.arrays import load_arrays
from datelier.io.types import ArrayOptions, CsvOptions, ImportResult
from datelier.pipeline import Sort


def inspect(table: pl.DataFrame) -> Inspection:
    dataset = Dataset.from_source(table, SourceReference(Path("unused"), 0, 0))
    return prepare_inspection(ImportResult(dataset, CsvOptions(), ()))


def test_ragged_numeric_lists_average_all_leaves_and_share_record_colors() -> None:
    data = inspect(
        pl.DataFrame({"values": [[[0.0, 2.0, 4.0], [100.0]], [[-1.0]], None]})
    )
    cells = [row[0] for row in data.first_page.cells]
    assert cells[0].number == 26.5 and cells[1].number == -1
    assert cells[2].is_null
    settings = InspectSettings(primary="values", supporting=("values",))
    card = prepare_record_page(
        data.dataset, prepare_records(data.dataset, settings), 0
    ).cards[0]
    assert card.primary and card.primary.cell == cells[0]
    assert card.fields[0].cell == cells[0]
    bounds = data.bounds[0]
    assert (bounds.minimum, bounds.maximum) == (-1, 26.5)
    assert cell_style(
        cells[0], bounds, TablePresentation(scale=NumericScale.LINEAR)
    ).rgba == pytest.approx((0.85, 0.35, 0.2))
    assert data.dataset.table["values"][0].to_list() == [[0.0, 2.0, 4.0], [100.0]]


def test_text_list_lengths_include_unicode_and_empty_text_and_exclude_nulls() -> None:
    cells = prepare_column_cells(
        pl.Series("text", [["🙂", "中文", "abcd", "", None], [], None]),
        ColumnRole.LIST_TEXT,
    )
    assert cells[0].text_length == 1.75 and cells[0].number is None
    assert "4 text lengths" in cells[0].note
    assert cells[1].text_length is None and not cells[1].is_null
    assert cells[2].is_null
    identifiers = prepare_column_cells(
        pl.Series([[1, 2], [3]]), ColumnRole.LIST_IDENTIFIER
    )
    assert all(cell.number is None for cell in identifiers)


def test_empty_nonfinite_fixed_and_extreme_container_values() -> None:
    cells = prepare_column_cells(
        pl.Series(
            "values",
            [[1.0, None, np.nan, np.inf, 3.0], [np.nan], [], None, [1e308, 1e308]],
        ),
        ColumnRole.LIST_NUMERIC,
    )
    assert cells[0].number == 2 and "2 nonfinite" in cells[0].note
    assert (
        cells[1].nonfinite
        and cell_style(cells[1], None, TablePresentation()).marker == "!"
    )
    assert not cells[2].is_null and cells[2].number is None
    assert cells[3].is_null and cells[4].number == pytest.approx(1e308)
    fixed = prepare_column_cells(
        pl.Series([[[1, 2], [3, 4]]], dtype=pl.Array(pl.Int64, (2, 2))),
        ColumnRole.LIST_NUMERIC,
    )
    assert fixed[0].number == 2.5


def test_numpy_means_load_only_on_request_and_follow_sorted_source_rows(
    tmp_path: Path,
) -> None:
    source = tmp_path / "arrays.npz"
    np.savez_compressed(
        source,
        values=np.array([[0.0, 2.0], [10.0, 20.0], [100.0, 200.0]]),
        image=np.array(
            [
                [[0.0, 2.0], [4.0, 6.0]],
                [[10.0, 20.0], [30.0, 40.0]],
                [[100.0, 200.0], [300.0, 400.0]],
            ]
        ),
        priority=np.array([2, 3, 1]),
    )
    original = source.read_bytes()
    editor = EditorController()
    try:
        file = editor.current
        file.open(source)
        until(editor, lambda: file.inspection is not None)
        assert file.inspection
        assert file.arrays.store.extractions == 0
        assert not file.inspection.first_page.array_ready
        assert file.inspection.first_page.cells[0][0].number is None
        file.pages.get(0)
        until(editor, lambda: bool((page := file.pages.get(0)) and page.array_ready))
        page = file.pages.get(0)
        assert page and page.cells[0][0].number == 1 and page.cells[0][1].number == 3
        assert file.arrays.store.extractions == 2
        file.editor.request(Sort(("priority",)))
        until(editor, lambda: not file.editor.busy)
        until(editor, lambda: bool((page := file.pages.get(0)) and page.array_ready))
        sorted_page = file.pages.get(0)
        assert sorted_page and sorted_page.row_ids == (2, 0, 1)
        assert [row[0].number for row in sorted_page.cells] == [150, 1, 15]
        file.records.settings = replace(
            file.records.settings, supporting=("values", "image"), gallery=False
        )
        until(
            editor,
            lambda: bool(
                file.records.jobs.active
                and file.records.jobs.active.settings.supporting == ("values", "image")
            ),
        )
        until(editor, lambda: file.records.jobs.get(0) is not None)
        records = file.records.jobs.get(0)
        assert records and records.cards[0].fields[0].cell == sorted_page.cells[0][0]
        assert records.cards[0].fields[1].cell == sorted_page.cells[0][1]
        assert source.read_bytes() == original
        assert not file.analysis.jobs.results and not editor.playback.snapshot.request
    finally:
        editor.close()


def test_nonfirst_record_axis_means_retain_complete_mapped_payload(
    tmp_path: Path,
) -> None:
    source = tmp_path / "mapped.npy"
    values = np.asfortranarray(np.arange(24, dtype=float).reshape(2, 3, 4))
    np.save(source, values)
    metadata = load_arrays(source)
    assert metadata.array_catalog
    mapping = ArrayRecordMapping(
        metadata.array_catalog.members[0].name,
        record_axis=1,
        layout=ArrayLayout.GENERIC,
        display_axes=(0, 2),
    )
    imported = load_arrays(source, ArrayOptions(mapping=mapping))
    assert imported.array_catalog
    settings = InspectSettings(supporting=("record_index",))
    records = prepare_records(imported.dataset, settings)
    page = prepare_array_record_page(
        imported.dataset,
        records,
        0,
        imported.array_catalog,
        array_mappings(imported),
        None,
    )
    for row, card in enumerate(page.cards):
        assert card.payload and card.payload.cell
        assert card.payload.cell.number == float(values[:, row, :].mean())
        assert card.row_id == row
        assert card.fields[0].cell and card.fields[0].cell.number is None


def test_streamed_numpy_extrema_and_unicode_means_are_finite(tmp_path: Path) -> None:
    source = tmp_path / "streamed.npz"
    numbers = np.asfortranarray(
        np.stack([np.full(49152, 1e308), np.full(49152, -1e308)])
    )
    np.savez_compressed(
        source, numbers=numbers, texts=np.array([["🙂", "中文"], ["abcd", ""]])
    )
    imported = load_arrays(source)
    page = prepare_array_page(prepare_inspection(imported), 0, 0, None)
    assert page.array_ready
    for row, expected in enumerate((1e308, -1e308)):
        cell = page.cells[row][0]
        assert cell.number == pytest.approx(expected) and cell.bounds
        assert np.isfinite(cell.bounds.percentile_low) and np.isfinite(
            cell.bounds.percentile_high
        )
        color = cell_style(cell, None, TablePresentation())
        assert color.rgba and all(0 <= value <= 1 for value in color.rgba)
    assert [row[1].text_length for row in page.cells] == [1.5, 2]
    assert np.array_equal(np.load(source)["numbers"], numbers)


def test_inspect_array_colors_share_the_containing_table_page_range(
    tmp_path: Path,
) -> None:
    source = tmp_path / "pages.npz"
    np.savez(source, values=np.arange(210).reshape(105, 2))
    imported = load_arrays(source)
    assert imported.array_catalog
    inspection = prepare_inspection(imported)
    table = prepare_array_page(inspection, 0, 0, None)
    settings = InspectSettings(supporting=("values",), count=105)
    records = prepare_records(imported.dataset, settings)
    detail = prepare_array_record_page(
        imported.dataset,
        records,
        8,
        imported.array_catalog,
        array_mappings(imported),
        None,
    )
    cell = detail.cards[0].fields[0].cell
    assert cell is not None
    assert cell == table.cells[8][0]
    assert cell_style(cell, None, TablePresentation()) == cell_style(
        table.cells[8][0], None, TablePresentation()
    )
    final_table = prepare_array_page(inspection, 100, 0, None)
    final_detail = prepare_array_record_page(
        imported.dataset,
        records,
        100,
        imported.array_catalog,
        array_mappings(imported),
        None,
    )
    assert final_detail.cards[0].fields[0].cell == final_table.cells[0][0]
