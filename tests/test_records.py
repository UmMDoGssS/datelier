from dataclasses import replace
from pathlib import Path
from time import monotonic, sleep

import polars as pl
import pytest

from datelier.core import Dataset, SourceReference
from datelier.inspection.presentation import TablePresentation, cell_style
from datelier.inspection.records import InspectSettings, RecordMode, RecordSet
from datelier.inspection.records.jobs import RecordJobs
from datelier.inspection.records.prepare import prepare_record_page, prepare_records
from datelier.pipeline import Comparison, Filter, Pipeline, Sort


def data() -> Dataset:
    return Dataset.from_source(
        pl.DataFrame(
            {
                "id": range(100),
                **{f"c{i}": [f"{i}-{r}" for r in range(100)] for i in range(40)},
            }
        ),
        SourceReference(Path("unused"), 0, 0),
    )


def test_range_and_seeded_random_identity_survive_row_reordering() -> None:
    source = data()
    sorted_data = Pipeline.start(source).apply(Sort(("id",), True)).current
    range_records = prepare_records(sorted_data, InspectSettings(start=3, count=4))
    assert range_records.positions.to_list() == [2, 3, 4, 5]
    assert range_records.row_ids.to_list() == [97, 96, 95, 94]
    random = InspectSettings(mode=RecordMode.RANDOM, count=10, seed=17)
    a = prepare_records(source, random)
    b = prepare_records(sorted_data, random)
    assert set(a.row_ids.to_list()) == set(b.row_ids.to_list()) and len(a.row_ids) == 10
    assert a.row_ids.equals(prepare_records(source, random).row_ids)
    filtered = (
        Pipeline.start(sorted_data).apply(Filter("id", Comparison.LT, 20)).current
    )
    selected = prepare_records(
        filtered, InspectSettings(mode=RecordMode.SELECTION), (5, 10, 50)
    )
    assert selected.row_ids.to_list() == [10, 5]
    assert selected.positions.to_list() == [9, 14]


def test_supporting_columns_are_not_limited_by_table_page_width() -> None:
    source = data()
    settings = InspectSettings(
        primary="c39", supporting=tuple(source.table.columns), start=2, count=1
    )
    records = prepare_records(source, settings)
    card = prepare_record_page(source, records, 0).cards[0]
    assert (card.row_id, card.position) == (1, 1)
    assert len(card.fields) == 41 and card.fields[-1].text == "39-1"
    assert card.primary and card.primary.name == "c39" and card.primary.text == "39-1"
    assert not prepare_records(source, replace(settings, start=1000)).positions.len()


def test_restored_inspect_fields_recover_against_already_bound_columns() -> None:
    from datelier.application.media.records import RecordController
    from datelier.core import SharedWorkers
    from datelier.plotting.scatter import LinkedSelection

    source = data()
    workers = SharedWorkers()
    controls = RecordController(LinkedSelection(), workers)
    try:
        controls.bind(source)
        controls.settings = InspectSettings(
            primary="missing", supporting=("c39", "missing"), gallery=False, seed=17
        )
        controls.bind(source)
        assert controls.settings.primary in source.table.columns
        assert controls.settings.supporting == ("c39",)
        assert not controls.settings.gallery and controls.settings.seed == 17
        records = prepare_records(source, controls.settings)
        assert prepare_record_page(source, records, 0).cards[0].fields[0].name == "c39"
        controls.settings = replace(controls.settings, supporting=())
        controls.bind(source)
        assert controls.settings.supporting == ()
    finally:
        controls.close()
        workers.shutdown()


def test_file_owned_record_jobs_reject_superseded_and_closed_pages() -> None:
    first, second = data(), data()
    jobs = RecordJobs()
    try:
        settings = InspectSettings(primary="c39", count=4)
        jobs.sync(first, settings, ())
        jobs.sync(second, replace(settings, start=3), ())
        deadline = monotonic() + 3
        while monotonic() < deadline:
            jobs.poll()
            page = jobs.get(0)
            if page:
                assert page.revision == second.revision and page.cards[0].row_id == 2
                break
            sleep(0.001)
        else:
            raise AssertionError(jobs.message)
        jobs.close()
        jobs.poll()
        assert jobs.active is None and jobs.get(0) is None
    finally:
        jobs.close()


def test_default_detailed_rows_include_every_type_and_match_preview_styles() -> None:
    from datelier.inspection.table import prepare_inspection
    from datelier.io.types import CsvOptions, ImportResult

    source = Dataset.from_source(
        pl.DataFrame(
            {
                "id": [1, 2],
                "number": [None, 5.0],
                "text": ["中🙂" * 3000, "A short sentence"],
                "image": ["one.png", "two.png"],
                "second_image": ["three.png", "four.png"],
                "nested": [[1, 2], []],
            }
        ),
        SourceReference(Path("unused"), 0, 0),
    )
    inspection = prepare_inspection(ImportResult(source, CsvOptions(), ()))
    card = prepare_record_page(
        source, prepare_records(source, InspectSettings()), 0
    ).cards[0]
    assert [field.name for field in card.fields] == source.table.columns
    assert card.fields[2].truncated and len(card.fields[2].text) == 4096
    assert card.fields[2].cell and card.fields[2].cell.text_length == 6000
    assert [field.reference for field in card.fields[3:5]] == ["one.png", "three.png"]
    bounds = {bound.column: bound for bound in inspection.bounds}
    for index, field in enumerate(card.fields):
        assert field.cell
        assert cell_style(
            field.cell, bounds.get(field.name), TablePresentation()
        ) == cell_style(
            inspection.first_page.cells[0][index],
            bounds.get(field.name),
            TablePresentation(),
        )


def test_shown_columns_exclude_tools_column_and_keep_sorted_field_identity() -> None:
    from datelier.application.media.records import RecordController
    from datelier.core import SharedWorkers
    from datelier.plotting.scatter import LinkedSelection

    source = Pipeline.start(data()).apply(Sort(("id",), True)).current
    workers = SharedWorkers()
    model = RecordController(LinkedSelection(), workers)
    try:
        model.bind(source)
        model.settings = replace(model.settings, supporting=("c39", "id"))
        model.show_tools("c3")
        card = prepare_record_page(
            source, prepare_records(source, model.settings), 0
        ).cards[0]
        assert card.row_id == 99
        assert [(field.name, field.text) for field in model.shown_fields(card)] == [
            ("c39", "39-99"),
            ("id", "99"),
        ]
        model.settings = replace(model.settings, supporting=())
        card = prepare_record_page(
            source, prepare_records(source, model.settings), 0
        ).cards[0]
        assert model.shown_fields(card) == ()
    finally:
        model.close()
        workers.shutdown()


def test_closing_during_record_preparation_safely_abandons_publication(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from threading import Event

    from datelier.core import SharedWorkers
    from datelier.inspection.records import jobs as module

    started, release = Event(), Event()
    original = module.prepare_records

    def blocked(
        dataset: Dataset, settings: InspectSettings, selection: tuple[int, ...]
    ) -> RecordSet:
        started.set()
        assert release.wait(3)
        return original(dataset, settings, selection)

    monkeypatch.setattr(module, "prepare_records", blocked)
    with SharedWorkers(workers=1) as workers:
        jobs = RecordJobs(workers)
        try:
            jobs.sync(data(), InspectSettings(), ())
            assert started.wait(3)
            future = jobs._future
            assert future
            jobs.close()
            assert not future.done()
            release.set()
            future.result(3)
            jobs.poll()
            assert jobs.active is None and jobs.get(0) is None
        finally:
            release.set()
            jobs.close()
