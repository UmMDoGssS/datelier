from pathlib import Path
from time import monotonic, sleep

import polars as pl
import pytest

from datelier.core.dataset import Dataset, SourceReference
from datelier.inspection import PAGE_COLUMNS, PAGE_ROWS, prepare_inspection
from datelier.io.csv import CsvImport, CsvOptions
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


def test_preview_worker_failure_is_visible_and_retryable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from datelier import preview

    dataset = Dataset.from_source(
        pl.DataFrame({"value": range(200)}), SourceReference(Path("table.csv"), 1, 1)
    )
    pages = PreviewCache()
    pages.bind(prepare_inspection(CsvImport(dataset, CsvOptions(), ())))
    original = preview.prepare_page

    def failed_page(dataset: Dataset, row: int, column: int = 0) -> None:
        raise RuntimeError("test preparation failed")

    monkeypatch.setattr(preview, "prepare_page", failed_page)
    try:
        pages.get(100)
        deadline = monotonic() + 3
        while not pages.error and monotonic() < deadline:
            pages.poll()
            sleep(0.001)
        assert "test preparation failed" in pages.error
        assert pages.get(0) is not None  # existing prepared data survives
        monkeypatch.setattr(preview, "prepare_page", original)
        pages.retry()
        deadline = monotonic() + 3
        while pages.get(100) is None and monotonic() < deadline:
            pages.poll()
            sleep(0.001)
        page = pages.get(100)
        assert page is not None
        assert page.row_ids[0] == 100
        assert not pages.error
    finally:
        pages.close()
