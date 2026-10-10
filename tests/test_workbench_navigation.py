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
from datelier.application.navigation import WorkbenchNavigation
from datelier.gui.editor_session import EditorSession
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
    editor = EditorSession()
    try:
        first = editor.active
        second = editor.new_tab()
        editor.comparisons = (ComparisonSettings(),)
        editor.navigation.choose_canvas(True)
        editor.activate(first.identity)
        assert not editor.navigation.comparing
        assert editor.comparisons == (ComparisonSettings(),)
        editor.navigation.choose_canvas(True)
        editor.activate(first.identity, focus=False)
        assert editor.navigation.comparing  # Per-frame selected-tab binding is idle.
        editor.close_tab(second.identity)
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
    editor = EditorSession()
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
        file.exploration.active_tab, file.exploration.tab = "Inspect", ""
        file.analysis.controls.start(
            file.analysis.jobs, file.loader.active.dataset, Algorithm.PCA
        )
        deadline = monotonic() + 5
        while file.analysis.pending_result is None and monotonic() < deadline:
            editor.poll()
            sleep(0.001)
        assert file.analysis.pending_result == Algorithm.PCA
        assert file.analysis.source is None
        assert file.exploration.active_tab == "Inspect" and file.exploration.tab == ""
        assert source.read_bytes() == original
    finally:
        editor.close()
