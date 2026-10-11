"""Navigation remains user-controlled when workers publish results."""

from pathlib import Path
from time import monotonic, sleep

import numpy as np

from datelier.analysis.jobs import AnalysisJobs
from datelier.analysis.types import (
    Algorithm,
    EmbeddingResult,
    PreparedInput,
    Provenance,
)
from datelier.application.sessions import EditorController, WorkbenchNavigation
from datelier.inspection.comparison_settings import ComparisonSettings
from datelier.io.loading import LoadPhase


def tiny_embedding(inputs: PreparedInput) -> EmbeddingResult:
    return EmbeddingResult(
        inputs.revision,
        inputs.row_ids,
        inputs.positions,
        inputs.values[:, :2],
        Provenance(inputs.request, inputs.summary, (), 0),
    )


def test_file_activation_exits_comparison_without_discarding_drafts() -> None:
    editor = EditorController()
    try:
        first = editor.active
        second = editor.new_file()
        editor.compare.columns.draft = ComparisonSettings()
        editor.navigation.choose_canvas(True)
        editor.activate(first.identity)
        assert not editor.navigation.comparing
        assert editor.compare.columns.draft == ComparisonSettings()
        editor.navigation.choose_canvas(True)
        editor.poll()
        assert editor.navigation.comparing  # Polling never activates a tab.
        editor.close_file(second.identity)
    finally:
        editor.close()


def test_navigation_defaults_and_drawer_are_independent() -> None:
    state = WorkbenchNavigation(context_open=True)
    state.choose_canvas(True)
    state.activate_file()
    assert not state.comparing and state.context_open and state.context_tab == "View"


def test_worker_completion_announces_result_without_changing_navigation(
    tmp_path: Path,
) -> None:
    source = tmp_path / "data.csv"
    rng = np.random.default_rng(8)
    source.write_text(
        "x,y\n" + "".join(f"{x},{y}\n" for x, y in rng.normal(size=(24, 2)))
    )
    original = source.read_bytes()
    editor = EditorController()
    file = editor.active
    try:
        file.loader.request(source)
        deadline = monotonic() + 5
        while file.loader.status.phase == LoadPhase.LOADING and monotonic() < deadline:
            editor.poll()
            sleep(0.001)
        assert file.loader.active is not None
        file.analysis.jobs.close()
        file.analysis.jobs = AnalysisJobs(tiny_embedding, executor=editor.workers)
        file.analysis.controls.features = ["x", "y"]
        editor.choose_route("Inspect")
        file.analysis.controls.start(
            file.analysis.jobs, file.loader.active.dataset, Algorithm.PCA
        )
        deadline = monotonic() + 5
        while file.analysis.pending_result is None and monotonic() < deadline:
            editor.poll()
            sleep(0.001)
        assert file.analysis.pending_result == Algorithm.PCA
        assert file.analysis.source is None
        assert file.views.tab == "Inspect"
        assert source.read_bytes() == original
    finally:
        editor.close()
