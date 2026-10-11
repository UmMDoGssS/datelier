"""Applied comparison recipes, independent drafts and original-row source links."""

import json
from collections.abc import Callable
from dataclasses import replace
from pathlib import Path
from time import monotonic, sleep

from datelier.application.comparisons.base import ComparisonFamily
from datelier.application.editor import EditorController
from datelier.application.workspace import capture_session
from datelier.inspection.audio.collections.settings import AudioCollectionSettings
from datelier.inspection.audio.comparisons.settings import (
    AudioComparisonSettings,
    AudioComparisonSource,
)
from datelier.inspection.comparison_settings import (
    ComparisonSettings,
    ComparisonSource,
    Normalization,
)
from datelier.inspection.images.comparisons.settings import (
    ImageComparisonSettings,
    ImageComparisonSource,
)
from datelier.inspection.images.profile_types import ImageProfileSettings
from datelier.inspection.text.comparisons.settings import (
    TextComparisonSettings,
    TextComparisonSource,
)
from datelier.io.types import ImportFormat, ObjectOptions
from datelier.pipeline.operations import Sort
from datelier.workspace.sessions.jobs import save_snapshot


def until(editor: EditorController, condition: Callable[[], bool]) -> None:
    deadline = monotonic() + 5
    while monotonic() < deadline:
        editor.poll()
        if condition():
            return
        sleep(0.001)
    raise AssertionError(editor.compare.columns.message)


def test_drafts_apply_independently_and_completed_selection_never_steals_focus(
    tmp_path: Path,
) -> None:
    first_path, second_path = tmp_path / "train.csv", tmp_path / "test.csv"
    first_path.write_text("x\n3.0\n0.0\n2.0\n1.0\n")
    second_path.write_text("different\n0.0\n3.0\n")
    originals = first_path.read_bytes(), second_path.read_bytes()
    editor = EditorController()
    try:
        first = editor.active
        first.open(first_path)
        second = editor.new_file(second_path)
        until(
            editor,
            lambda: first.inspection is not None and second.inspection is not None,
        )
        first.editor.request(Sort(("x",)))
        until(editor, lambda: not first.editor.busy)
        model = editor.compare.columns
        model.map_files((first.identity, second.identity))
        editor.choose_route("Compare files")
        editor.compare.tab = ComparisonFamily.COLUMNS
        editor.poll()
        assert model.changed and model.jobs.started == 0 and model.active is None
        model.draft = replace(model.draft, bins=2, normalization=Normalization.COUNT)
        model.apply()
        until(editor, lambda: model.active is not None)
        result = model.active
        assert result and [s.counts.tolist() for s in result.series] == [[2, 2], [1, 1]]
        assert editor.navigation.comparing and editor.active is second
        model.draft = replace(model.draft, bins=4)
        editor.activate(first.identity)
        editor.choose_route("Compare files")
        editor.poll()
        assert (
            model.active is result
            and model.draft.bins == 4
            and result.settings.bins == 2
        )
        model.select(0, 0)
        assert editor.active is first and not editor.navigation.comparing
        editor.activate(second.identity)
        until(editor, lambda: first.selection.row_ids == {1, 3})
        assert editor.active is second and first.table.target_row == 1
        editor.saved_session = replace(
            editor.saved_session,
            text_comparisons=(
                TextComparisonSettings(
                    (TextComparisonSource(second.identity, "different"),)
                ),
            ),
            image_comparisons=(
                ImageComparisonSettings(
                    (
                        ImageComparisonSource(
                            second.identity, ImageProfileSettings(column="different")
                        ),
                    )
                ),
            ),
            audio_comparisons=(
                AudioComparisonSettings(
                    (
                        AudioComparisonSource(
                            second.identity, AudioCollectionSettings(column="different")
                        ),
                    )
                ),
            ),
        )
        editor.close_file(second.identity)
        editor.poll()
        assert len(model.recipes[0].sources) == len(model.draft.sources) == 1
        assert (
            model.active is None
            and model.message == "Map columns from at least two files."
        )
        assert originals == (first_path.read_bytes(), second_path.read_bytes())
    finally:
        editor.close()


def test_named_view_labels_scope_and_saved_column_viewport_restore(
    tmp_path: Path,
) -> None:
    object_path, table_path = tmp_path / "records.json", tmp_path / "other.csv"
    object_path.write_text(json.dumps({"rows": [{"x": 3.0}, {"x": 1.0}, {"x": 2.0}]}))
    table_path.write_text("different\n1.0\n3.0\n")
    workspace = tmp_path / "session.json"
    editor = EditorController()
    try:
        owner = editor.active
        owner.open(object_path, ObjectOptions(), format=ImportFormat.OBJECT)
        until(editor, lambda: owner.objects.root is not None)
        view = owner.record_views.open(owner, ("rows",))
        other = editor.new_file(table_path)
        until(
            editor, lambda: view.inspection is not None and other.inspection is not None
        )
        model = editor.compare.columns
        model.draft = ComparisonSettings(
            (
                ComparisonSource(view.identity, "x"),
                ComparisonSource(other.identity, "different"),
            ),
            bins=2,
        )
        model.apply()
        until(editor, lambda: model.active is not None)
        result = model.active
        assert result and result.series[0].origin.view == view.view_name
        assert view.view_name in result.series[0].label
        model.select(0, 0)
        until(editor, lambda: bool(view.selection.row_ids))
        assert editor.active is owner and editor.current is view
        assert owner.selection.row_ids == frozenset()
        model.height = 335
        model.selected_source = model.selected_bin = 1
        save_snapshot(workspace, capture_session(editor), False)
    finally:
        editor.close()
    reopened = EditorController()
    try:
        reopened.open_workspace(workspace)
        until(
            reopened,
            lambda: (
                not reopened.workspace.busy
                and reopened.compare.columns.active is not None
            ),
        )
        assert reopened.compare.columns.height == 335
        assert (
            reopened.compare.columns.selected_source
            == reopened.compare.columns.selected_bin
            == 1
        )
        assert (
            reopened.compare.columns.active
            and reopened.compare.columns.active.series[0].origin.view != "table"
        )
        owner = reopened.files[0]
        view = owner.record_views.files[0]
        owner.record_views.close_view(view.identity)
        saved = capture_session(reopened)
        assert saved.workspace.comparisons[0].sources[0].file_id != view.identity
        assert all(
            not file.analysis.jobs.results
            and file.text.corpus.profile is None
            and file.images.profile_jobs.active is None
            and file.audio.collection.active is None
            for file in reopened.all_files
        )
    finally:
        reopened.close()


def test_export_ports_capture_the_named_view_and_protect_a_pending_source(
    tmp_path: Path,
) -> None:
    import polars as pl

    from datelier.gui.components.probe import GuiProbe
    from datelier.gui.shell.page import WorkbenchPage
    from datelier.io.exporting import ExportFormat

    source, next_source, output = (
        tmp_path / "records.json",
        tmp_path / "next.csv",
        tmp_path / "export.csv",
    )
    source.write_text(json.dumps({"rows": [{"x": 3.0}, {"x": 1.0}]}))
    next_source.write_text("different\n7.0\n8.0\n")
    original = next_source.read_bytes()
    editor = EditorController()
    page = WorkbenchPage(editor, GuiProbe())
    try:
        owner = editor.active
        owner.open(source, ObjectOptions(), format=ImportFormat.OBJECT)
        until(editor, lambda: owner.objects.root is not None)
        view = owner.record_views.open(owner, ("rows",))
        until(editor, lambda: view.inspection is not None)
        port = page.export_dialog.capture()
        assert port and view.view_name in port.label and "records.json" in port.label
        port.request(output, ExportFormat.CSV, False)
        until(editor, lambda: not view.exporter.busy)
        assert pl.read_csv(output)["x"].to_list() == [3.0, 1.0]
        owner.open(next_source)
        # The captured view may close when the next source publishes. Queue the
        # explicit export while its scope remains live; the destination guard
        # includes both the pending source and all current datasets.
        port.request(next_source, ExportFormat.CSV, True)
        until(editor, lambda: not view.exporter.busy)
        assert next_source.read_bytes() == original and view.exporter.result is None
        assert (
            "source files" in view.exporter.message
            or "closed" in view.exporter.message.lower()
        )
    finally:
        page.close()
        editor.close()
