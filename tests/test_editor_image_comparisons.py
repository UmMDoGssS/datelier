"""Saved scopes/views, explicit preparation, scoped links and partial recovery."""

from pathlib import Path
from time import monotonic, sleep
from unittest.mock import patch

import pytest
from PIL import Image

from datelier.gui.editor_session import EditorSession
from datelier.inspection.images.comparisons.settings import (
    ImageComparisonSettings,
    ImageComparisonSource,
    ImageComparisonViewSettings,
)
from datelier.inspection.images.profile_types import ImageProfileSettings
from datelier.inspection.references.types import ReferenceSettings
from datelier.io.loading import LoadPhase
from datelier.workspace.codec import decode_record, encode
from datelier.workspace.session_storage import read_session_workspace
from datelier.workspace.session_types import SessionFile, SessionWorkspace


def wait(editor: EditorSession, root: Path) -> None:
    deadline = monotonic() + 5
    while monotonic() < deadline:
        editor.poll()
        for file in editor.file_sessions:
            if file.loader.active is not None and file.references.settings.roots != (
                str(root),
            ):
                file.references.configure(ReferenceSettings(roots=(str(root),)))
        if (
            not editor.opening.busy
            and not editor.workspace_jobs.busy
            and not editor.image_comparison_jobs.busy
            and all(
                file.loader.status.phase != LoadPhase.LOADING
                and not file.references.busy
                for file in editor.files
            )
        ):
            return
        sleep(0.001)
    raise AssertionError("Image comparison editor did not settle")


def test_legacy_session_defaults_preserve_empty_image_comparisons() -> None:
    workspace = SessionWorkspace((SessionFile("empty"),), "empty")
    raw = encode(workspace)
    assert isinstance(raw, dict)
    for key in (
        "image_comparisons",
        "image_comparison_index",
        "image_comparison_view",
        "comparison_tab",
    ):
        raw.pop(key)
    assert decode_record(SessionWorkspace, raw) == workspace


def test_saved_image_comparison_reopens_idle_links_correct_file_and_recovers(
    tmp_path: Path,
) -> None:
    for name, width, red in (
        ("a2", 2, 10),
        ("a4", 4, 30),
        ("b6", 6, 50),
        ("b2", 2, 70),
    ):
        Image.new("RGB", (width, 2), (red, 20, 30)).save(tmp_path / f"{name}.png")
    paths = (tmp_path / "first.csv", tmp_path / "second.csv")
    paths[0].write_text("image\na2.png\na4.png\n")
    paths[1].write_text("image\nb6.png\nb2.png\n")
    workspace = tmp_path / "session.datelier.json"
    editor = EditorSession()
    try:
        editor.opening.request(paths, editor.active_id)
        wait(editor, tmp_path)
        first, second = editor.files
        recipe = ImageComparisonSettings(
            tuple(
                ImageComparisonSource(file.identity, ImageProfileSettings("image"))
                for file in editor.files
            ),
            bins=2,
        )
        view = ImageComparisonViewSettings(
            tab="Colors", mode="RGB", dtype="|u1", channel="R", source=1, height=200
        )
        editor.image_comparisons = (recipe,)
        editor.image_comparison_view = view
        editor.comparison_tab = "Images"
        editor.poll()
        assert (
            editor.image_comparison_jobs.started == 0
            and editor.image_comparison_jobs.active is None
        )
        editor.image_comparison_jobs.request()
        wait(editor, tmp_path)
        result = editor.image_comparison_jobs.active
        assert result is not None
        editor.select_image_comparison(result, 1, "Width", 1)
        deadline = monotonic() + 5
        while not second.selection.row_ids and monotonic() < deadline:
            editor.poll()
            sleep(0.001)
        assert second.selection.row_ids == {0} and not first.selection.row_ids
        assert editor.active is second and second.table.target_row == 1
        editor.open_image_comparison_record(result, 0, 1)
        assert editor.active is first and first.selection.row_ids == {1}
        assert first.inspect.settings.focus == 0 and first.focus_inspect
        assert first.table.target_row == 2
        assert first.exploration.tab == "Inspect"
        editor.save_workspace(workspace)
        wait(editor, tmp_path)
        saved = read_session_workspace(workspace)
        assert (
            saved.image_comparisons == (recipe,) and saved.image_comparison_view == view
        )
        assert saved.comparison_tab == "Images"
        assert (
            "curves" not in workspace.read_text()
            and "channel_records" not in workspace.read_text()
        )
        paths[0].rename(tmp_path / "moved.csv")
        with patch(
            "datelier.inspection.images.comparisons.jobs.prepare_comparison",
            side_effect=AssertionError("restore profiled images"),
        ):
            editor.open_workspace(workspace)
            wait(editor, tmp_path)
        failed, good = editor.files
        assert failed.recovery and good.loader.active
        assert (
            editor.image_comparisons == (recipe,)
            and editor.image_comparison_view == view
        )
        assert editor.comparison_tab == "Images"
        with pytest.raises(ValueError, match="changed"):
            editor.open_image_comparison_record(result, 0, 1)
        assert (
            editor.image_comparison_jobs.active is None
            and not editor.image_comparison_jobs.busy
        )
        assert editor.image_comparison_jobs.started == 1
        editor.recover_source(failed.identity, relink=tmp_path / "moved.csv")
        wait(editor, tmp_path)
        assert failed.loader.active and editor.image_comparison_jobs.active is None
        editor.close_tab(failed.identity)
        assert editor.image_comparisons[0].sources == (recipe.sources[1],)
        assert editor.image_comparison_jobs.active is None
        editor.save_workspace(tmp_path / "closed.datelier.json")
        wait(editor, tmp_path)
        assert (
            editor.workspace_jobs.saved
            and editor.workspace_jobs.saved.path.name == "closed.datelier.json"
        )
    finally:
        editor.close()
