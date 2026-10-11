"""Contextual imports reset only their own recipe; layouts recover coherently."""

from pathlib import Path
from time import monotonic, sleep

import pytest

from datelier.application.editor import EditorController
from datelier.io.loading import LoadPhase
from datelier.io.types import CsvOptions, ImportFormat
from datelier.pipeline.operations import Sort
from datelier.workspace.preferences import (
    Preferences,
    Theme,
    read_preferences,
    save_preferences,
)
from datelier.workspace.storage import save_workspace
from datelier.workspace.types import Workspace


def wait(editor: EditorController) -> None:
    deadline = monotonic() + 5
    while monotonic() < deadline:
        editor.poll()
        if (
            not editor.opening.busy
            and not editor.workspace.busy
            and all(
                file.loader.status.phase != LoadPhase.LOADING and not file.editor.busy
                for file in editor.files
            )
        ):
            return
        sleep(0.001)
    raise AssertionError("Editor action did not finish")


def test_contextual_import_changes_only_owner_and_failed_reload_retains_recipe(
    tmp_path: Path,
) -> None:
    custom, sibling = tmp_path / "custom.csv", tmp_path / "sibling.csv"
    custom.write_text("x;y\n3;6\n1;2\n")
    sibling.write_text("x,y\n10,20\n")
    editor = EditorController()
    try:
        file = editor.active
        file.imports.path, file.imports.csv.separator = str(custom), ";"
        file.imports.request()
        wait(editor)
        assert (
            file.loader.active is not None
            and file.loader.active.dataset.table.columns == ["x", "y"]
        )
        other = editor.new_file(sibling)
        wait(editor)
        other_revision = other.loader.revision
        file.editor.request(Sort(("x",)))
        wait(editor)
        assert file.editor.pipeline is not None and file.editor.pipeline.cursor == 1
        file.imports.csv.text_only = True
        file.imports.request()
        wait(editor)
        assert file.editor.pipeline is not None and file.editor.pipeline.cursor == 0
        assert file.loader.active.dataset.table["x"].to_list() == ["3", "1"]
        custom.write_text('x;y\n"unclosed;2\n')
        revision = file.loader.revision
        file.imports.request()
        wait(editor)
        assert (
            file.loader.revision == revision and other.loader.revision == other_revision
        )
        assert editor.active is other
        before = sibling.read_bytes()
        editor.save_workspace(sibling, "", (), False, True)
        wait(editor)
        assert "source data" in editor.workspace.message
        assert sibling.read_bytes() == before
        editor.close_file(file.identity)
        with pytest.raises(ValueError, match="Finish"):
            file.imports.request()
    finally:
        editor.close()


def test_old_panel_layout_recovers_other_preferences(tmp_path: Path) -> None:
    path = tmp_path / "preferences.json"
    layout = (
        "[Window][Table preview]\n[Window][Workspace]\n"
        "[Docking][Data]\nDockSpace ID=1\n"
    )
    save_preferences(path, Preferences(theme=Theme.LIGHT, layout=layout))
    preferences, message = read_preferences(path)
    assert preferences.layout == "" and preferences.theme == Theme.LIGHT
    assert "layout reset" in message


def test_workspace_save_protects_another_file_and_aliases(tmp_path: Path) -> None:
    from datelier.io.importing import load_file
    from datelier.workspace.storage import reference_source

    source, other = tmp_path / "a.csv", tmp_path / "b.csv"
    source.write_text("x\n1\n")
    other.write_text("x\n2\n")
    imported = load_file(source)
    recipe = Workspace(
        reference_source(imported.dataset.source), ImportFormat.CSV, CsvOptions()
    )
    alias = tmp_path / "alias.json"
    alias.symlink_to(other)
    before = other.read_bytes()
    with pytest.raises(ValueError, match="source data"):
        save_workspace(alias, recipe, sources=(other,))
    assert other.read_bytes() == before
