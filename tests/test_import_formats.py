from pathlib import Path

import pytest
from polars.testing import assert_frame_equal

from datelier.import_csv import CsvOptions, load_csv, load_tsv
from datelier.import_types import ImportFailure, ImportFormat
from datelier.importing import load_file
from datelier.inspection import prepare_inspection


def test_tsv_matches_csv_and_prepares_preview(tmp_path: Path) -> None:
    csv = tmp_path / "table.csv"
    tsv = tmp_path / "table[1].TSV"
    csv.write_text('row_id,value,label\n4,1.5,"hello, world"\n7,,café\n')
    content = "row_id\tvalue\tlabel\n4\t1.5\thello, world\n7\t\tcafé\n"
    tsv.write_text(content)
    imported = load_file(tsv)
    assert imported.format == ImportFormat.TSV
    assert_frame_equal(imported.dataset.table, load_csv(csv).dataset.table)
    assert imported.dataset.row_ids.to_list() == [0, 1]
    inspection = prepare_inspection(imported)
    assert inspection.first_page.rows[1] == ("7", "NULL", "café")
    assert inspection.schema[1].null_count == 1
    assert tsv.read_text() == content


def test_explicit_format_and_tsv_options(tmp_path: Path) -> None:
    path = tmp_path / "table.data"
    path.write_text("skip\n2026-10-04\t'quoted\ttext'\tNA\n")
    options = CsvOptions(
        separator="\t",
        quote_char="'",
        has_header=False,
        skip_rows=1,
        null_values=("NA",),
        try_parse_dates=True,
    )
    imported = load_file(path, options, format=ImportFormat.TSV)
    assert imported.options == options
    assert str(imported.dataset.table.dtypes[0]) == "Date"
    assert imported.dataset.table.row(0)[1:] == ("quoted\ttext", None)
    with pytest.raises(ImportFailure, match="Unsupported extension"):
        load_file(path)


@pytest.mark.parametrize("content", ["", "a\tb\n1\t2\t3\n", 'a\n"bad\n'])
def test_malformed_tsv_has_format_diagnostic(tmp_path: Path, content: str) -> None:
    path = tmp_path / "bad.tsv"
    path.write_text(content)
    with pytest.raises(ImportFailure, match="TSV"):
        load_tsv(path)
    assert path.read_text() == content
