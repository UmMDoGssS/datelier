from pathlib import Path
from time import monotonic, sleep

import polars as pl

from datelier.dataset import Dataset, SourceReference
from datelier.import_csv import CsvImport, CsvOptions
from datelier.inspection import PAGE_COLUMNS, PAGE_ROWS, prepare_inspection
from datelier.preview import PreviewCache


def test_preview_pages_are_bounded_aligned_and_invalidated() -> None:
    table = pl.DataFrame({f"c{i}": range(1000) for i in range(35)})
    dataset = Dataset.from_source(table, SourceReference(Path("table.csv"), 1, 1))
    inspection = prepare_inspection(CsvImport(dataset, CsvOptions(), ()))
    pages = PreviewCache()
    pages.bind(inspection)
    try:
        first = pages.get(0)
        assert first is not None
        assert len(first.rows) == PAGE_ROWS
        assert len(first.columns) == PAGE_COLUMNS
        for start in range(100, 800, 100):
            assert pages.get(start, 32) is None
            deadline = monotonic() + 3
            while pages.get(start, 32) is None and monotonic() < deadline:
                pages.poll()
                sleep(0.001)
            page = pages.get(start, 32)
            assert page is not None
            assert page.columns == ("c32", "c33", "c34")
            assert page.row_ids[0] == start
            assert page.rows[0] == (str(start),) * 3
            assert pages.page_count <= 4
        pages.get(900)  # a pending old page must not survive a new revision
        changed = dataset.with_rows(table.head(1), dataset.row_ids.head(1))
        pages.bind(prepare_inspection(CsvImport(changed, CsvOptions(), ())))
        pages.poll()
        page = pages.get(0)
        assert page is not None
        assert page.revision == changed.revision
        assert len(page.rows) == 1
        assert pages.page_count == 1
    finally:
        pages.close()
