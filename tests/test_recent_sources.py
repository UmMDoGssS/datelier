"""Recent recipe persistence, independent recovery and source-safe preferences."""

import json
from pathlib import Path
from time import monotonic, sleep

import pytest

from datelier.application.imports import ImportController
from datelier.application.sessions import EditorController
from datelier.io.loading import LoadPhase
from datelier.io.types import (
    CsvOptions,
    ImportFormat,
    JsonOptions,
    ParquetOptions,
    XmlOptions,
)
from datelier.pipeline.operations import Sort
from datelier.workspace.preferences import (
    Preferences,
    Theme,
    read_preferences,
    save_preferences,
)
from datelier.workspace.recent import MAX_RECENT, RecentKind, RecentSource, remember
from datelier.workspace.sessions import SourceDraft


def wait(editor: EditorController) -> None:
    deadline = monotonic() + 5
    while monotonic() < deadline:
        editor.poll()
        if (
            not editor.opening.busy
            and not editor.workspace.busy
            and editor.preferences.ready
            and all(
                file.loader.status.phase != LoadPhase.LOADING and not file.editor.busy
                for file in editor.files
            )
        ):
            return
        sleep(0.001)
    raise AssertionError("Recent opening did not finish")


def test_bounded_recent_recipes_round_trip_and_section_recovery(tmp_path: Path) -> None:
    entries: tuple[RecentSource, ...] = ()
    for index in range(MAX_RECENT + 5):
        entries = remember(
            entries,
            RecentSource(
                str(tmp_path / f"{index}.csv"),
                format=ImportFormat.CSV,
                options=CsvOptions(separator=";"),
            ),
        )
    first = entries[-1]
    entries = remember(entries, first)
    workspace = RecentSource(str(tmp_path / "session.json"), RecentKind.WORKSPACE)
    entries = remember(entries, workspace)
    assert len(entries) == MAX_RECENT and entries[:2] == (workspace, first)
    path = tmp_path / "preferences.json"
    original = Preferences(theme=Theme.LIGHT, recent=entries)
    save_preferences(path, original)
    assert read_preferences(path)[0] == original
    raw = json.loads(path.read_text())
    raw["recent"].insert(1, {"kind": "RecentSource", "path": "invalid"})
    path.write_text(json.dumps(raw))
    restored, message = read_preferences(path)
    assert restored.theme == Theme.LIGHT and restored.recent[:2] == entries[:2]
    assert "recent entry skipped" in message


def test_recent_reopen_uses_exact_recipe_and_failure_retry_preserves_siblings(
    tmp_path: Path,
) -> None:
    source, missing = tmp_path / "custom.csv", tmp_path / "missing.csv"
    source.write_text("x;y\n1;2\n3;4\n")
    options = CsvOptions(separator=";")
    entry = RecentSource(str(source), format=ImportFormat.CSV, options=options)
    prefs = tmp_path / "preferences.json"
    save_preferences(prefs, Preferences(recent=(entry,)))
    editor = EditorController(prefs)
    try:
        wait(editor)
        editor.open_recent(editor.preferences.value.recent[0])
        wait(editor)
        good = editor.active
        assert (
            good.loader.active is not None
            and good.loader.active.dataset.table.columns == ["x", "y"]
        )
        revision = good.loader.revision
        editor.new_file()
        failure = RecentSource(str(missing), format=ImportFormat.CSV, options=options)
        editor.open_recent(failure)
        wait(editor)
        failed = editor.active
        assert failed.loader.status.phase == LoadPhase.FAILED
        assert "missing" in failed.loader.status.message.lower()
        assert failed.imports.path == str(missing)
        assert failed.imports.csv.build() == options
        missing.write_text("x;y\n5;6\n")
        editor.open_recent(failure)
        wait(editor)
        assert editor.active is failed and len(editor.files) == 2
        assert (
            failed.loader.active is not None
            and failed.loader.active.dataset.table.columns == ["x", "y"]
        )
        good.editor.request(Sort(("x",), descending=True))
        wait(editor)
        assert editor.preferences.value.recent[0].path == str(missing)
        editor.open_recent(entry)
        wait(editor)
        assert editor.active is good and good.loader.revision != revision
        assert editor.preferences.value.recent[0] == entry
        assert editor.source_paths == (source, missing)
        before = missing.read_bytes()
        with pytest.raises(ValueError, match="source data"):
            save_preferences(
                missing, editor.preferences.value, sources=editor.source_paths
            )
        assert missing.read_bytes() == before
    finally:
        editor.close()


def test_saved_and_reopened_workspace_is_recent_and_can_recover_source(
    tmp_path: Path,
) -> None:
    source, moved, workspace = (
        tmp_path / "data.csv",
        tmp_path / "moved.csv",
        tmp_path / "session.json",
    )
    source.write_text("x,y\n1,2\n3,4\n")
    editor = EditorController()
    try:
        editor.opening.request((source,), editor.active_id)
        wait(editor)
        identity = editor.active.identity
        editor.save_workspace(workspace, "", (), False, False)
        wait(editor)
        recent = editor.preferences.value.recent[0]
        assert recent == RecentSource(str(workspace), RecentKind.WORKSPACE)
        editor.close_file(editor.active_id)
        source.rename(moved)
        editor.open_recent(recent)
        wait(editor)
        file = editor.active
        assert file.recovery is not None and file.loader.active is None
        editor.recover(file.identity, moved, False)
        wait(editor)
        assert (
            file.loader.active is not None
            and file.loader.active.dataset.source.path == moved
        )
        assert not file.analysis.jobs.busy and not file.analysis.jobs.results
        editor.new_file()
        editor.open_recent(recent)
        wait(editor)
        assert len(editor.files) == 1 and editor.active.identity == identity
        assert editor.active.recovery is not None
    finally:
        editor.close()


@pytest.mark.parametrize(
    "format,options",
    [
        (
            ImportFormat.CSV,
            CsvOptions(
                separator=";",
                null_values=("N|A",),
                infer_schema_length=None,
                quote_char=None,
                skip_rows=1,
            ),
        ),
        (ImportFormat.JSONL, JsonOptions(True)),
        (ImportFormat.PARQUET, ParquetOptions(("a|b", "c"))),
        (
            ImportFormat.XML,
            XmlOptions(
                ".//row",
                (("x", "urn:namespace|value"),),
                False,
                False,
                ("N|A",),
                False,
                True,
            ),
        ),
    ],
)
def test_import_controls_retain_exact_bound_recipe_until_edited(
    format: ImportFormat,
    options: CsvOptions | JsonOptions | ParquetOptions | XmlOptions,
) -> None:
    controls = ImportController(lambda _: None)
    controls.bind(SourceDraft("source.csv", format, options))
    assert controls.selected == format and controls.drafts[format].build() == options
    if isinstance(options, CsvOptions):
        controls.csv.separator = ","
        changed = controls.drafts[format].build()
        assert isinstance(changed, CsvOptions) and changed.separator == ","


def test_failed_source_becomes_protected_before_retry(tmp_path: Path) -> None:
    source = tmp_path / "failed.json"
    editor = EditorController()
    try:
        editor.active.open(source, JsonOptions())
        wait(editor)
        assert editor.active.loader.status.phase == LoadPhase.FAILED
        source.write_text('[{"x":1}]')
        original = source.read_bytes()
        assert editor.source_paths == (source,)
        editor.save_workspace(source, "", (), False, True)
        wait(editor)
        assert "source data" in editor.workspace.message
        with pytest.raises(ValueError, match="source data"):
            save_preferences(
                source, editor.preferences.value, sources=editor.source_paths
            )
        assert source.read_bytes() == original
    finally:
        editor.close()
