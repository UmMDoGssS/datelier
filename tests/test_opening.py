from pathlib import Path
from threading import Event
from time import monotonic, sleep

import pytest

from datelier.application.sessions import EditorController
from datelier.io.catalog import DirectoryListing, list_directory
from datelier.io.jobs import LoadPhase
from datelier.io.types import CsvOptions, ImportFormat


def wait(editor: EditorController) -> None:
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
    editor = EditorController()
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
    editor = EditorController()
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
    from datelier.io.jobs import opening

    source = tmp_path / "good.csv"
    source.write_text("x,y\n1,2\n3,4\n")
    started, release = Event(), Event()
    original = opening.resolve_sources

    def blocked(paths: tuple[Path, ...]) -> tuple[Path, ...]:
        started.set()
        assert release.wait(3)
        return original(paths)

    monkeypatch.setattr(opening, "resolve_sources", blocked)
    editor = EditorController()
    try:
        owner = editor.active
        editor.opening.request((source,), owner.identity)
        assert started.wait(3)
        editor.close_file(owner.identity)
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
    from datelier.application import browser as browser_module

    older, newer = tmp_path / "older", tmp_path / "newer"
    older.mkdir()
    newer.mkdir()
    (older / "old.csv").write_text("x\n1\n")
    (newer / "new.csv").write_text("x\n2\n")
    started, release = Event(), Event()
    original = browser_module.list_directory

    def blocked(path: Path) -> DirectoryListing:
        if path == older:
            started.set()
            assert release.wait(3)
        return original(path)

    monkeypatch.setattr(browser_module, "list_directory", blocked)
    editor = EditorController()
    browser = editor.browser
    try:
        browser.path = str(older)
        browser.browse()
        assert started.wait(3)
        browser.request(newer)
        deadline = monotonic() + 3
        while browser.busy and monotonic() < deadline:
            browser.poll()
            sleep(0.001)
        assert browser.listing is not None
        assert browser.listing.directory == newer
        release.set()
        browser.poll()
        assert browser.listing.directory == newer
        browser.request(tmp_path / "absent")
        deadline = monotonic() + 3
        while browser.busy and monotonic() < deadline:
            browser.poll()
            sleep(0.001)
        assert browser.listing is None and "retry" in browser.message
        started.clear()
        release.clear()
        browser.request(older)
        assert started.wait(3)
        browser.cancel()
        release.set()
        browser.poll()
        assert not browser.busy and browser.listing is None
        browser.close()
        browser.close()
        with pytest.raises(ValueError, match="closed"):
            browser.request(newer)
    finally:
        release.set()
        editor.close()


def test_browser_search_selection_aliases_and_path_drafts(tmp_path: Path) -> None:
    source = tmp_path / "Mixed##case.csv"
    source.write_text("metadata only")
    alias = tmp_path / "Alias.csv"
    alias.symlink_to(source)
    (tmp_path / "other.txt").write_text("text")
    (tmp_path / "folder").mkdir()
    editor = EditorController()
    try:
        browser = editor.browser
        browser.request(tmp_path)
        deadline = monotonic() + 3
        while browser.busy and monotonic() < deadline:
            browser.poll()
            sleep(0.001)
        assert browser.listing and len(browser.entries) == 4
        browser.search = "cAsE"
        browser.poll()
        assert [e.name for e in browser.shown] == [source.name]
        browser.select_all()
        assert browser.selected_paths() == (source,)
        browser.search = ".csv"
        browser.poll()
        browser.select_all()
        assert browser.selected_paths() == (source,)
        browser.toggle(source)
        with pytest.raises(ValueError, match="Choose"):
            browser.selected_paths()
        with pytest.raises(ValueError, match="available"):
            browser.toggle(tmp_path / "absent.csv")
        browser.direct = "  ~/literal##name.csv  "
        assert browser.direct_paths() == (Path("~/literal##name.csv"),)
        assert browser.collection_paths() == (tmp_path,)
        browser.cancel()
        assert browser.direct == "  ~/literal##name.csv  " and browser.search == ".csv"
        browser.parent()
        assert browser.path == str(tmp_path.parent) and not browser.selected
        assert source.read_text() == "metadata only"
        assert editor.active.inspection is None
    finally:
        editor.close()


def test_duplicate_open_after_failed_reload_preserves_the_usable_source(
    tmp_path: Path,
) -> None:
    good, missing = tmp_path / "good.csv", tmp_path / "missing.csv"
    good.write_text("x\n1\n")
    editor = EditorController()
    try:
        file = editor.active
        file.open(good)
        wait(editor)
        revision = file.loader.revision
        file.open(missing)
        wait(editor)
        assert file.loader.status.phase == LoadPhase.FAILED
        assert editor.source_paths == (missing, good)
        editor.new_file()
        editor.open_paths((good,))
        wait(editor)
        assert len(editor.files) == 2 and editor.active is file
        assert file.loader.revision == revision
        assert file.inspection and file.inspection.dataset.source.path == good
    finally:
        editor.close()


def test_recent_retry_does_not_replace_an_executing_import(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from datelier.io import importing
    from datelier.io.types import ImportOptions, ImportResult

    source = tmp_path / "source.csv"
    source.write_text("x\n1\n")
    started, release = Event(), Event()
    original = importing.load_inspectable_file

    def blocked(
        path: Path,
        options: ImportOptions | None = None,
        *,
        format: ImportFormat | None = None,
    ) -> ImportResult:
        started.set()
        assert release.wait(3)
        return original(path, options, format=format)

    # The loader's default adapter imports lazily inside its worker boundary.
    monkeypatch.setattr(importing, "load_inspectable_file", blocked)
    from datelier.io.jobs import loading

    monkeypatch.setattr(loading, "load_inspectable_file", blocked)
    editor = EditorController()
    try:
        file = editor.active
        file.open(source)
        assert started.wait(3)
        generation = file.loader.generation
        editor.opening.request((source,), file.identity, retry=True)
        deadline = monotonic() + 3
        while editor.opening.busy and monotonic() < deadline:
            editor.poll()
            sleep(0.001)
        assert not editor.opening.busy and "before retrying" in editor.opening.message
        assert file.loader.generation == generation
        release.set()
        wait(editor)
        assert file.inspection and file.inspection.dataset.table["x"].to_list() == [1]
    finally:
        release.set()
        editor.close()
