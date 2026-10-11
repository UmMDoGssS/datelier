from pathlib import Path

import pytest
from polars.testing import assert_frame_equal

from datelier.inspection.table import prepare_inspection
from datelier.io.importing import load_file
from datelier.io.tabular import CsvOptions, load_csv, load_tsv
from datelier.io.types import ImportFailure, ImportFormat


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


@pytest.mark.parametrize("suffix", ["csv", "tsv", "json", "jsonl", "parquet"])
def test_cross_format_schema_values_and_prepared_preview(
    tmp_path: Path, suffix: str
) -> None:
    import polars as pl

    expected = pl.DataFrame(
        {"id": [1, 2], "value": [1.5, None], "label": ["café", "last"]}
    )
    path = tmp_path / ("equivalent." + suffix)
    if suffix in ("csv", "tsv"):
        expected.write_csv(path, separator="\t" if suffix == "tsv" else ",")
    elif suffix == "json":
        expected.write_json(path)
    elif suffix == "jsonl":
        expected.write_ndjson(path)
    else:
        expected.write_parquet(path)
    content = path.read_bytes()
    imported = load_file(path)
    assert_frame_equal(imported.dataset.table, expected)
    inspection = prepare_inspection(imported)
    assert inspection.first_page.row_ids == (0, 1)
    assert inspection.first_page.rows == (("1", "1.5", "café"), ("2", "NULL", "last"))
    assert [s.null_count for s in inspection.schema] == [0, 1, 0]
    assert path.read_bytes() == content


def test_xml_matches_common_tabular_fixture(tmp_path: Path) -> None:
    import polars as pl

    path = tmp_path / "equivalent.xml"
    path.write_text(
        "<rows><row><id>1</id><value>1.5</value><label>café</label></row>"
        "<row><id>2</id><value/><label>last</label></row></rows>"
    )
    expected = pl.DataFrame(
        {"id": [1, 2], "value": [1.5, None], "label": ["café", "last"]}
    )
    assert_frame_equal(load_file(path).dataset.table, expected)


@pytest.mark.parametrize("suffix", ["csv", "tsv", "json", "jsonl", "parquet", "xml"])
def test_each_format_failure_preserves_active_inspection(
    tmp_path: Path, suffix: str
) -> None:
    from time import monotonic, sleep

    from datelier.io.loading import DatasetLoader, LoadPhase

    valid = tmp_path / "valid.csv"
    valid.write_text("id\n9\n")
    bad = tmp_path / ("bad." + suffix)
    bad.write_bytes(b"not valid tabular data\xff")
    loader = DatasetLoader()

    def wait() -> None:
        deadline = monotonic() + 3
        while loader.status.phase == LoadPhase.LOADING and monotonic() < deadline:
            loader.poll()
            sleep(0.001)
        assert loader.status.phase != LoadPhase.LOADING

    try:
        loader.request(valid)
        wait()
        active = loader.active
        assert active is not None
        loader.request(bad)
        wait()
        assert loader.status.phase == LoadPhase.FAILED
        assert loader.active is active
        assert active.dataset.table["id"].to_list() == [9]
        assert bad.read_bytes() == b"not valid tabular data\xff"
    finally:
        loader.close()


@pytest.mark.parametrize("suffix", ["tsv", "json", "jsonl", "parquet", "xml"])
def test_shared_guard_rejects_changed_sources(
    tmp_path: Path, suffix: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    import os

    import polars as pl

    path = tmp_path / ("table." + suffix)
    table = pl.DataFrame({"id": [1]})
    if suffix == "tsv":
        table.write_csv(path, separator="\t")
    elif suffix == "json":
        table.write_json(path)
    elif suffix == "jsonl":
        table.write_ndjson(path)
    elif suffix == "parquet":
        table.write_parquet(path)
    else:
        path.write_text("<rows><row><id>1</id></row></rows>")
    original_stat = Path.stat
    calls = 0

    def changed_stat(target: Path, *, follow_symlinks: bool = True) -> os.stat_result:
        nonlocal calls
        if target == path:
            calls += 1
            if calls == 2:
                path.write_bytes(path.read_bytes() + b" ")
        return original_stat(target, follow_symlinks=follow_symlinks)

    monkeypatch.setattr(Path, "stat", changed_stat)
    with pytest.raises(ImportFailure, match="changed during import"):
        load_file(path)


@pytest.mark.parametrize(
    "format",
    [ImportFormat.JSON, ImportFormat.JSONL, ImportFormat.PARQUET, ImportFormat.XML],
)
def test_wrong_option_family_is_rejected(tmp_path: Path, format: ImportFormat) -> None:
    with pytest.raises(ImportFailure, match="requires"):
        load_file(tmp_path / "unused.data", CsvOptions(), format=format)


@pytest.mark.parametrize("suffix", ["csv", "tsv", "json", "jsonl", "parquet"])
def test_literal_column_names_cannot_select_other_columns(
    tmp_path: Path, suffix: str
) -> None:
    import polars as pl

    from datelier.inspection.table import prepare_page

    expected = pl.DataFrame(
        {"^x$": [1, None], "x": [2, 3], "^y.*$": [4, 5], "y.other": [6, 7]}
    )
    path = tmp_path / ("names." + suffix)
    if suffix in ("csv", "tsv"):
        expected.write_csv(path, separator="\t" if suffix == "tsv" else ",")
    elif suffix == "json":
        expected.write_json(path)
    elif suffix == "jsonl":
        expected.write_ndjson(path)
    else:
        expected.write_parquet(path)
    imported = load_file(path)
    assert_frame_equal(imported.dataset.table, expected)
    inspection = prepare_inspection(imported)
    assert inspection.first_page.columns == tuple(expected.columns)
    assert inspection.first_page.rows == (("1", "2", "4", "6"), ("NULL", "3", "5", "7"))
    assert prepare_page(imported.dataset, 1, 2).rows == (("5", "7"),)
