"""Explicit execution, late completion abandonment and source-scoped selections."""

from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from pathlib import Path
from threading import Event
from time import monotonic, sleep

import pytest
from audio_comparison_fixtures import fixture

from datelier.inspection.audio.collections.settings import AudioScope, AudioScopeMode
from datelier.inspection.audio.comparisons import AudioComparisonSettings
from datelier.inspection.audio.comparisons.jobs import AudioComparisonJobs
from datelier.inspection.audio.comparisons.types import AudioComparisonInput


def wait(
    jobs: AudioComparisonJobs,
    inputs: tuple[AudioComparisonInput, ...],
    recipe: AudioComparisonSettings,
) -> None:
    deadline = monotonic() + 5
    while monotonic() < deadline:
        jobs.bind(recipe, inputs)
        jobs.poll()
        if not jobs.busy:
            assert jobs.active is not None, jobs.message
            return
        sleep(0.001)
    raise AssertionError(jobs.message)


def test_binding_never_runs_and_closed_or_changed_inputs_drop_late_results(
    tmp_path: Path,
) -> None:
    inputs, recipe = fixture(tmp_path)
    gate = Event()
    with ThreadPoolExecutor(max_workers=1) as pool:
        pool.submit(gate.wait)
        jobs = AudioComparisonJobs(pool)
        try:
            jobs.bind(recipe, inputs)
            assert jobs.started == 0 and not jobs.busy
            jobs.request()
            assert jobs.busy
            jobs.bind(recipe, inputs[:1])
            assert not jobs.busy and jobs.active is None
            gate.set()
            with pytest.raises(ValueError, match="two"):
                jobs.request()
            jobs.bind(recipe, inputs)
            assert not jobs.busy and jobs.started == 1
            jobs.request()
            wait(jobs, inputs, recipe)
            result = jobs.active
            assert result is not None
            current = inputs[0].dataset
            changed = (
                replace(
                    inputs[0], dataset=current.with_rows(current.table, current.row_ids)
                ),
                inputs[1],
            )
            jobs.bind(recipe, changed)
            assert jobs.active is None and jobs.started == 2 and not jobs.busy
            jobs.bind(recipe, inputs)
            jobs.request()
            jobs.close()
            pool.submit(lambda: None).result(timeout=5)
            jobs.bind(recipe, inputs)
            assert jobs.active is None and not jobs.busy
        finally:
            gate.set()
            jobs.close()


def test_selection_publication_is_scoped_and_rejects_closed_sources(
    tmp_path: Path,
) -> None:
    inputs, recipe = fixture(tmp_path)
    jobs = AudioComparisonJobs()
    try:
        jobs.bind(recipe, inputs)
        jobs.request()
        wait(jobs, inputs, recipe)
        result = jobs.active
        assert result is not None
        curve = next(c for c in result.curves if c.metric.name == "Duration")
        jobs.request_selection(result, 1, curve.metric, 0, inputs[1].dataset)
        deadline = monotonic() + 5
        selection = None
        while monotonic() < deadline and selection is None:
            selection = jobs.poll_selection(
                {i.source.file_id: i.dataset for i in inputs}
            )
            sleep(0.001)
        assert (
            selection is not None
            and selection.origin.file_id == "test"
            and selection.row_ids == (0,)
        )
        jobs.request_selection(result, 1, curve.metric, 0, inputs[1].dataset)
        while monotonic() < deadline and "obsolete" not in jobs.selection_message:
            assert jobs.poll_selection({"train": inputs[0].dataset}) is None
            sleep(0.001)
        assert "obsolete" in jobs.selection_message
    finally:
        jobs.close()


def test_linked_scope_changes_invalidate_but_unrelated_selection_does_not(
    tmp_path: Path,
) -> None:
    inputs, recipe = fixture(tmp_path)
    source = replace(
        inputs[0].source,
        profile=replace(
            inputs[0].source.profile, scope=AudioScope(AudioScopeMode.SELECTION)
        ),
    )
    recipe = replace(recipe, sources=(source, inputs[1].source))
    inputs = (replace(inputs[0], source=source, selection=(0,)), inputs[1])
    jobs = AudioComparisonJobs()
    try:
        jobs.bind(recipe, inputs)
        jobs.request()
        wait(jobs, inputs, recipe)
        result = jobs.active
        unrelated = (inputs[0], replace(inputs[1], selection=(1,)))
        jobs.bind(recipe, unrelated)
        assert jobs.active is result and jobs.started == 1
        jobs.bind(recipe, (replace(inputs[0], selection=(1,)), unrelated[1]))
        assert jobs.active is None and not jobs.busy and jobs.started == 1
    finally:
        jobs.close()
