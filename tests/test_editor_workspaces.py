"""Editor snapshots, source-specific recovery and obsolete session publication."""

from pathlib import Path
from threading import Event, current_thread, main_thread
from time import monotonic, sleep

import pytest

from datelier.core.dataset import SourceReference
from datelier.gui.editor_session import EditorSession
from datelier.inspection.comparison_settings import ComparisonSettings, ComparisonSource
from datelier.io.importing import load_file
from datelier.io.loading import DatasetLoader, LoadPhase
from datelier.io.types import ImportOptions, ImportResult
from datelier.pipeline.operations import Sort
from datelier.workspace.session_restore import (
    RestoredSession,
    RestoredSessionFile,
    SourceRecovery,
)
from datelier.workspace.session_storage import read_session_workspace
from datelier.workspace.session_types import SessionFile
from datelier.workspace.types import WorkspaceSource


def wait(editor: EditorSession) -> None:
    deadline = monotonic() + 5
    while monotonic() < deadline:
        editor.poll()
        if (
            not editor.opening.busy
            and not editor.workspace_jobs.busy
            and all(
                file.loader.status.phase != LoadPhase.LOADING and not file.editor.busy
                for file in editor.files
            )
        ):
            return
        sleep(0.001)
    raise AssertionError("Editor workspace jobs did not finish")


def saved_session(tmp_path: Path) -> Path:
    train, test = tmp_path / "train.csv", tmp_path / "test.csv"
    train.write_text("x,y\n3,6\n1,2\n2,4\n")
    test.write_text("a,b\n10,20\n30,40\n")
    path = tmp_path / "session.datelier"
    editor = EditorSession()
    try:
        editor.opening.request((train, test), editor.active_id)
        wait(editor)
        first, second = editor.files
        first.editor.request(Sort(("x",)))
        wait(editor)
        first.plots.bins, second.plots.bins = 7, 13
        first.plots.custom_scatter = True
        first.analysis.controls.seed, second.analysis.controls.seed = 17, 29
        assert first.loader.revision is not None
        first.selection.choose(first.loader.revision, (1,))
        blank = editor.new_tab()
        editor.reorder((second.identity, blank.identity, first.identity))
        editor.activate(first.identity)
        editor.comparisons = (
            ComparisonSettings(
                (
                    ComparisonSource(first.identity, "x"),
                    ComparisonSource(second.identity, "a"),
                )
            ),
        )
        editor.save_workspace(path)
        wait(editor)
        assert editor.workspace_jobs.saved is not None
    finally:
        editor.close()
    return path


def test_editor_save_restore_and_partial_source_recovery(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from datelier.workspace import session_jobs

    original = session_jobs.reference_source

    def worker_fingerprint(source: SourceReference) -> WorkspaceSource:
        assert current_thread() is not main_thread()
        return original(source)

    # Capture is GUI-independent and never fingerprints in the caller's thread.
    monkeypatch.setattr(session_jobs, "reference_source", worker_fingerprint)
    path = saved_session(tmp_path)
    saved = read_session_workspace(path)
    editor = EditorSession()
    try:
        old = editor.active
        editor.open_workspace(path)
        wait(editor)
        assert old.closed and tuple(file.identity for file in editor.files) == tuple(
            file.identity for file in saved.files
        )
        first, second, train = editor.files
        assert first.plots.bins == 13 and train.plots.bins == 7
        assert first.analysis.controls.seed == 29 and train.analysis.controls.seed == 17
        assert train.selection.row_ids == {1} and not first.selection.row_ids
        assert second.loader.active is None and editor.active is train
        assert editor.comparisons == saved.comparisons
        moved = tmp_path / "moved.csv"
        (tmp_path / "train.csv").rename(moved)
        editor.open_workspace(path)
        wait(editor)
        good, _, failed = editor.files
        assert good.loader.active is not None and failed.recovery is not None
        revision = good.loader.revision
        editor.activate(good.identity)
        editor.recover_source(failed.identity, relink=moved)
        wait(editor)
        assert good.loader.revision == revision and editor.active is good
        assert failed.recovery is None and failed.loader.active is not None
        assert failed.selection.row_ids == {1} and failed.analysis.controls.seed == 17
        assert all(
            not file.analysis.jobs.busy and not file.analysis.jobs.results
            for file in editor.files
        )
    finally:
        editor.close()


def test_closed_recovery_owner_cannot_publish_into_replacement(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from datelier.workspace import session_jobs

    path = saved_session(tmp_path)
    moved = tmp_path / "moved.csv"
    (tmp_path / "train.csv").rename(moved)
    started, release = Event(), Event()
    original = session_jobs.restore_session_file

    def blocked(file: SessionFile, recovery: SourceRecovery) -> RestoredSessionFile:
        started.set()
        assert release.wait(3)
        return original(file, recovery)

    monkeypatch.setattr(session_jobs, "restore_session_file", blocked)
    editor = EditorSession()
    try:
        editor.open_workspace(path)
        wait(editor)
        failed = editor.files[2]
        editor.recover_source(failed.identity, relink=moved)
        assert started.wait(3)
        editor.close_tab(failed.identity)
        replacement = editor.new_tab()
        release.set()
        wait(editor)
        assert (
            failed.closed
            and replacement.loader.active is None
            and replacement.recovery is None
        )
        assert editor.files[0].loader.active is not None
    finally:
        release.set()
        editor.close()


def test_restore_is_obsolete_when_blank_owner_starts_a_new_import(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from datelier.workspace import session_jobs

    path = saved_session(tmp_path)
    started, release, load_started, load_release = Event(), Event(), Event(), Event()
    original = session_jobs.restore_session_workspace

    def blocked_restore(path: Path) -> RestoredSession:
        started.set()
        assert release.wait(3)
        return original(path)

    def blocked_import(path: Path, options: ImportOptions | None) -> ImportResult:
        load_started.set()
        assert load_release.wait(3)
        return load_file(path, options)

    monkeypatch.setattr(session_jobs, "restore_session_workspace", blocked_restore)
    editor = EditorSession(loader_override=DatasetLoader(importer=blocked_import))
    try:
        blank = editor.active
        editor.open_workspace(path)
        assert started.wait(3)
        blank.loader.request(tmp_path / "test.csv")
        assert load_started.wait(3)
        release.set()
        deadline = monotonic() + 3
        while editor.workspace_jobs.busy and monotonic() < deadline:
            editor.poll()
            sleep(0.001)
        assert editor.files == [blank] and blank.loader.active is None
        assert "obsolete" in editor.workspace_jobs.message
        load_release.set()
        wait(editor)
        assert blank.loader.active is not None and editor.active is blank
    finally:
        release.set()
        load_release.set()
        editor.close()


def test_failed_whole_session_open_or_source_destination_retains_usable_tabs(
    tmp_path: Path,
) -> None:
    path = saved_session(tmp_path)
    editor = EditorSession()
    try:
        editor.open_workspace(path)
        wait(editor)
        files = tuple(editor.files)
        active = editor.active
        revision = active.loader.revision
        missing = tmp_path / "missing.datelier"
        editor.open_workspace(missing)
        wait(editor)
        assert tuple(editor.files) == files and editor.active is active
        assert active.loader.revision == revision
        assert "Session workspace failed" in editor.workspace_jobs.message
        source = tmp_path / "test.csv"
        before = source.read_bytes()
        editor.save_workspace(source, overwrite=True)
        wait(editor)
        assert (
            source.read_bytes() == before
            and "source data" in editor.workspace_jobs.message
        )
        assert tuple(editor.files) == files and active.loader.revision == revision
    finally:
        editor.close()


def test_changed_source_requires_acceptance_and_reports_view_selection_adjustments(
    tmp_path: Path,
) -> None:
    path = saved_session(tmp_path)
    source = tmp_path / "train.csv"
    source.write_text("x\n30\n10\n20\n")
    editor = EditorSession()
    try:
        editor.open_workspace(path)
        wait(editor)
        good, _, changed = editor.files
        assert changed.recovery is not None and changed.recovery.changed
        revision = good.loader.revision
        editor.recover_source(changed.identity)
        wait(editor)
        assert changed.recovery is not None and changed.loader.active is None
        editor.recover_source(changed.identity, accept_changed=True)
        wait(editor)
        assert changed.loader.active is not None and changed.recovery is None
        assert changed.loader.active.dataset.table["x"].to_list() == [10, 20, 30]
        assert (
            not changed.selection.row_ids
            and "adjusted" in changed.loader.status.message
        )
        assert not changed.plots.custom_scatter and good.loader.revision == revision
    finally:
        editor.close()


def test_reference_controls_restore_without_payloads(tmp_path: Path) -> None:
    from dataclasses import replace

    from datelier.inspection.references.types import ReferenceMapping
    from datelier.workspace.codec import decode_record, encode
    from datelier.workspace.types import WorkspaceViews

    source = tmp_path / "media.csv"
    source.write_text("image\na.png\nb.png\n")
    path = tmp_path / "preview.datelier"
    editor = EditorSession(initial_path=source)
    try:
        editor.active.loader.request(source)
        wait(editor)
        file = editor.active
        settings = replace(
            file.references.settings,
            roots=(str(tmp_path),),
            thumbnail_size=64,
            mappings=(
                ReferenceMapping("image", "a.png", str(tmp_path / "chosen.png")),
            ),
        )
        file.references.configure(settings)
        file.reference_view.thumbnails = False
        editor.save_workspace(path)
        wait(editor)
        editor.open_workspace(path)
        wait(editor)
        assert editor.active.references.settings == settings
        assert not editor.active.reference_view.thumbnails
        assert not editor.active.references.previews
        assert not editor.active.analysis.jobs.results
        legacy = encode(WorkspaceViews())
        assert isinstance(legacy, dict)
        legacy.pop("references")
        legacy.pop("thumbnails")
        decoded = decode_record(WorkspaceViews, legacy)
        assert decoded.references.roots == () and decoded.thumbnails
    finally:
        editor.close()
