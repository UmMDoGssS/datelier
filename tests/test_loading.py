from pathlib import Path
from threading import Event
from time import monotonic, sleep

import pytest

from datelier.import_csv import CsvImport, CsvOptions, load_csv
from datelier.inspection import CELL_CHARACTERS, prepare_inspection, prepare_page
from datelier.loading import DatasetLoader, LoadPhase


def await_load(loader: DatasetLoader) -> None:
    deadline = monotonic() + 3
    while loader.status.phase == LoadPhase.LOADING and monotonic() < deadline:
        loader.poll()
        sleep(0.001)
    assert loader.status.phase != LoadPhase.LOADING


def test_prepared_pages_and_schema(tmp_path: Path) -> None:
    path = tmp_path / "fixture.csv"
    path.write_text('id,text,value\n1,"a\nb",\n2,' + "x" * 400 + ",3\n")
    inspection = prepare_inspection(load_csv(path))
    assert [(s.name, s.dtype, s.null_count) for s in inspection.schema] == [
        ("id", "Int64", 0),
        ("text", "String", 0),
        ("value", "Int64", 1),
    ]
    page = inspection.first_page
    assert page.row_ids == (0, 1)
    assert page.rows[0] == ("1", "a\\nb", "NULL")
    assert len(page.rows[1][1]) == CELL_CHARACTERS + 1
    assert prepare_page(inspection.dataset, 1, 1).rows[0][1] == "3"
    assert prepare_page(inspection.dataset, 2).rows == ()
    with pytest.raises(ValueError):
        prepare_page(inspection.dataset, -1)


def test_newer_load_wins_even_when_old_parser_finishes_later(tmp_path: Path) -> None:
    old, new = tmp_path / "old.csv", tmp_path / "new.csv"
    old.write_text("v\n1\n")
    new.write_text("v\n2\n")
    started, release = Event(), Event()

    def importer(path: Path, options: CsvOptions) -> CsvImport:
        if path == old:
            started.set()
            assert release.wait(3)
        return load_csv(path, options)

    loader = DatasetLoader(importer)
    try:
        loader.request(old)
        assert started.wait(3)
        assert not loader.poll()  # polling never waits for the parser
        loader.request(new)
        await_load(loader)
        assert loader.active is not None
        revision = loader.active.dataset.revision
        assert loader.active.dataset.table["v"].to_list() == [2]
        assert loader.retired_running == 1
        release.set()
        deadline = monotonic() + 3
        while loader.retired_running and monotonic() < deadline:
            loader.poll()
            sleep(0.001)
        assert loader.retired_running == 0
        assert loader.active.dataset.revision == revision
    finally:
        release.set()
        loader.close()


def test_failure_and_abandonment_preserve_active_data(tmp_path: Path) -> None:
    path = tmp_path / "ok.csv"
    path.write_text("v\n1\n")
    loader = DatasetLoader()
    try:
        loader.request(path)
        await_load(loader)
        active = loader.active
        loader.request(tmp_path / "missing.csv")
        await_load(loader)
        assert loader.status.phase == LoadPhase.FAILED
        assert "Could not read source" in loader.status.message
        assert loader.active is active
        loader.request(path)
        loader.abandon()
        assert loader.status.phase == LoadPhase.ABANDONED
        assert "may still finish" in loader.status.message
        loader.poll()
        assert loader.active is active
    finally:
        loader.close()
    with pytest.raises(RuntimeError, match="closed"):
        loader.request(path)


def test_revision_change_rejects_pending_result(tmp_path: Path) -> None:
    path = tmp_path / "ok.csv"
    path.write_text("v\n1\n")
    loader = DatasetLoader()
    try:
        loader.request(path)
        loader.active = prepare_inspection(load_csv(path))
        active = loader.active
        await_load(loader)
        assert loader.status.phase == LoadPhase.ABANDONED
        assert loader.active is active
    finally:
        loader.close()


def test_rapid_requests_cancel_obsolete_queued_work(tmp_path: Path) -> None:
    path = tmp_path / "latest.csv"
    path.write_text("v\n3\n")
    first_started, second_started, release = Event(), Event(), Event()
    seen: list[str] = []

    def importer(source: Path, options: CsvOptions) -> CsvImport:
        seen.append(source.name)
        if source.name in ("first.csv", "second.csv"):
            (first_started if source.name == "first.csv" else second_started).set()
            assert release.wait(3)
            raise RuntimeError("An obsolete parser failed")
        return load_csv(source, options)

    loader = DatasetLoader(importer)
    try:
        loader.request(tmp_path / "first.csv")
        assert first_started.wait(3)
        loader.request(tmp_path / "second.csv")
        assert second_started.wait(3)
        for number in range(20):
            loader.request(tmp_path / f"queued-{number}.csv")
        loader.request(path)
        assert loader.retired_running == 2
        release.set()
        await_load(loader)
        assert loader.status.phase == LoadPhase.READY
        assert loader.active is not None
        assert loader.active.dataset.table["v"].to_list() == [3]
        assert set(seen) == {"first.csv", "second.csv", "latest.csv"}
    finally:
        release.set()
        loader.close()
