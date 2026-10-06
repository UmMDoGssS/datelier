from pathlib import Path
from threading import Event
from time import monotonic, sleep

import pytest

from datelier.gui.editor_session import EditorSession
from datelier.io.catalog import DirectoryListing, list_directory
from datelier.io.loading import LoadPhase
from datelier.io.types import CsvOptions, ImportFormat


def wait(editor: EditorSession) -> None:
    deadline = monotonic() + 5
    while monotonic() < deadline:
        editor.poll()
        if not editor.opening.busy and all(
            file.loader.status.phase != LoadPhase.LOADING for file in editor.files
        ):
            return
        sleep(0.001)
    raise AssertionError("Opening did not finish")


def test_directory_listing_opens_supported_regular_files(
    tmp_path: Path,
) -> None:
    (tmp_path / "subfolder").mkdir()
    (tmp_path / "a.CSV").write_text("not parsed during listing")
    (tmp_path / "b.ndjson").write_text("also not parsed")
    (tmp_path / "ignored.txt").write_text("text")
    (tmp_path / "alias.csv").symlink_to(tmp_path / "a.CSV")
    (tmp_path / "broken.csv").symlink_to(tmp_path / "absent.csv")
    listing = list_directory(tmp_path)
    assert listing.folders == (tmp_path / "subfolder",)
    assert [(file.name, file.format) for file in listing.files] == [
        ("a.CSV", ImportFormat.CSV),
        ("alias.csv", ImportFormat.CSV),
        ("b.ndjson", ImportFormat.JSONL),
        ("ignored.txt", ImportFormat.MEDIA),
    ]
    assert listing.files[0].path == listing.files[1].path
    with pytest.raises(OSError):
        list_directory(tmp_path / "absent")
    with pytest.raises(OSError):
        list_directory(tmp_path / "a.CSV")


def test_multi_open_reuses_blank_and_focuses_already_open_source(
    tmp_path: Path,
) -> None:
    train, test = tmp_path / "train.csv", tmp_path / "test.csv"
    train.write_text("x,y\n1,2\n3,4\n")
    test.write_text("x,y\n10,20\n30,40\n")
    alias = tmp_path / "alias.csv"
    alias.symlink_to(train)
    editor = EditorSession()
    try:
        blank = editor.active
        editor.opening.request((train, test, train), blank.identity)
        wait(editor)
        assert len(editor.files) == 2 and editor.files[0] is blank
        assert all(file.loader.active is not None for file in editor.files)
        first = editor.files[0]
        first.plots.bins = 9
        revision = first.loader.revision
        editor.opening.request((alias,), editor.active.identity)
        wait(editor)
        assert len(editor.files) == 2 and editor.active is first
        assert first.loader.revision == revision and first.plots.bins == 9
    finally:
        editor.close()


def test_failed_import_is_independent_and_can_retry_with_options(
    tmp_path: Path,
) -> None:
    good, malformed = tmp_path / "good.csv", tmp_path / "other.csv"
    good.write_text("x,y\n1,2\n3,4\n")
    malformed.write_text('x,y\n"unclosed,2\n')
    before = good.read_bytes()
    editor = EditorSession()
    try:
        editor.opening.request((good, malformed), editor.active.identity)
        wait(editor)
        usable, failed = editor.files
        assert usable.loader.active is not None
        assert (
            failed.loader.active is None
            and failed.loader.status.phase == LoadPhase.FAILED
        )
        revision = usable.loader.revision
        malformed.write_text("x;y\n10;20\n30;40\n")
        editor.opening.request(
            (malformed,),
            failed.identity,
            format=ImportFormat.CSV,
            options=CsvOptions(separator=";"),
            retry=True,
        )
        wait(editor)
        assert len(editor.files) == 2 and failed.loader.active is not None
        assert failed.loader.active.dataset.table.columns == ["x", "y"]
        assert usable.loader.revision == revision and good.read_bytes() == before
    finally:
        editor.close()


def test_closed_origin_abandons_executing_open_resolution(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from datelier.io import opening

    source = tmp_path / "good.csv"
    source.write_text("x,y\n1,2\n3,4\n")
    started, release = Event(), Event()
    original = opening.resolve_sources

    def blocked(paths: tuple[Path, ...]) -> tuple[Path, ...]:
        started.set()
        assert release.wait(3)
        return original(paths)

    monkeypatch.setattr(opening, "resolve_sources", blocked)
    editor = EditorSession()
    try:
        owner = editor.active
        editor.opening.request((source,), owner.identity)
        assert started.wait(3)
        editor.close_tab(owner.identity)
        replacement = editor.active
        release.set()
        wait(editor)
        assert owner.closed and editor.files == [replacement]
        assert replacement.loader.active is None
        assert "closed" in editor.opening.message
    finally:
        release.set()
        editor.close()


def test_folder_retry_newer_listing_and_cancellation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from datelier.gui import file_browser

    older, newer = tmp_path / "older", tmp_path / "newer"
    older.mkdir()
    newer.mkdir()
    (older / "old.csv").write_text("x\n1\n")
    (newer / "new.csv").write_text("x\n2\n")
    started, release = Event(), Event()
    original = file_browser.list_directory

    def blocked(path: Path) -> DirectoryListing:
        if path == older:
            started.set()
            assert release.wait(3)
        return original(path)

    monkeypatch.setattr(file_browser, "list_directory", blocked)
    editor = EditorSession()
    browser = editor.browser
    try:
        browser.path = str(older)
        browser.open(editor.active_id, folder=True)
        assert started.wait(3)
        browser.request_directory(newer)
        deadline = monotonic() + 3
        while browser.busy and monotonic() < deadline:
            browser.poll()
            sleep(0.001)
        assert browser.listing is not None
        assert browser.listing.directory == newer and browser.folder_mode
        release.set()
        browser.poll()
        assert browser.listing.directory == newer
        browser.request_directory(tmp_path / "absent")
        while browser.busy and monotonic() < deadline:
            browser.poll()
            sleep(0.001)
        assert browser.listing is None and "retry" in browser.message
        browser.request_directory(newer)
        editor.close_tab(editor.active_id)
        assert not browser.visible and not browser.busy and browser.owner is None
    finally:
        release.set()
        editor.close()
