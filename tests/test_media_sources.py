from pathlib import Path

import pytest
from PIL import Image

from datelier.core.column_roles import ColumnRole
from datelier.io.importing import load_file
from datelier.io.types import ImportFailure, ImportFormat, MediaOptions
from datelier.pipeline.history import Pipeline
from datelier.pipeline.operations import Sort
from datelier.workspace.single import Workspace
from datelier.workspace.single.restore import SourceIssue, restore_workspace
from datelier.workspace.single.storage import reference_source, save_workspace


def test_direct_file_metadata_does_not_decode_and_text_lines_are_explicit(
    tmp_path: Path,
) -> None:
    image = tmp_path / "broken.png"
    image.write_bytes(b"undecodable")
    imported = load_file(image)
    assert imported.format == ImportFormat.MEDIA
    assert imported.dataset.table["path"].to_list() == [str(image)]
    assert imported.dataset.role("path").role == ColumnRole.IMAGE
    assert imported.dataset.table["size_bytes"][0] == 11
    assert imported.dataset.row_ids.to_list() == [0]
    text = tmp_path / "note.txt"
    text.write_bytes("hello 世界\r\n\r\nlast line".encode())
    default = load_file(text)
    assert (
        default.dataset.table.height == 1 and default.dataset.table["text"][0] is None
    )
    lines = load_file(text, MediaOptions(text_lines=True))
    assert lines.dataset.table["text"].to_list() == ["hello 世界", "", "last line"]
    assert lines.dataset.table["line"].to_list() == [1, 2, 3]
    assert lines.dataset.role("text").role == ColumnRole.TEXT
    assert lines.dataset.row_ids.to_list() == [0, 1, 2]
    text.write_bytes(b"\xff")
    with pytest.raises(ImportFailure, match="utf-8"):
        load_file(text, MediaOptions(text_lines=True))
    text.write_bytes(b"")
    assert load_file(text, MediaOptions(text_lines=True)).dataset.table.height == 0


def test_folder_manifest_roundtrip_missing_member_and_relink(tmp_path: Path) -> None:
    folder = tmp_path / "media"
    folder.mkdir()
    (folder / "sub").mkdir()
    for name in ("a.png", "sub/a.png"):
        Image.new("RGB", (2, 3)).save(folder / name)
    (folder / "sub/loop").symlink_to(folder, target_is_directory=True)
    imported = load_file(folder)
    assert imported.dataset.table["member"].to_list() == ["a.png", "sub/a.png"]
    assert imported.dataset.role("path").role == ColumnRole.IMAGE
    assert isinstance(imported.options, MediaOptions) and imported.options.manifest == (
        "a.png",
        "sub/a.png",
    )
    pipeline = Pipeline.start(imported.dataset).apply(Sort(("member",), True))
    workspace = Workspace(
        reference_source(imported.dataset.source),
        imported.format,
        imported.options,
        pipeline.history,
        pipeline.cursor,
    )
    saved = tmp_path / "media.datelier"
    save_workspace(saved, workspace)
    restored = restore_workspace(saved)
    assert restored.pipeline.current.row_ids.to_list() == [1, 0]
    assert restored.pipeline.current.table.equals(pipeline.current.table)
    (folder / "a.png").unlink()
    with pytest.raises(SourceIssue, match="changed"):
        restore_workspace(saved)
    accepted = restore_workspace(saved, accept_changed=True)
    assert accepted.pipeline.current.row_ids.to_list() == [1, 0]
    assert accepted.pipeline.source.table["member"].to_list() == ["a.png", "sub/a.png"]
    assert accepted.pipeline.source.table["size_bytes"][0] is None
    assert any(
        "Missing/unreadable" in d for d in accepted.inspection.imported.diagnostics
    )
    moved = tmp_path / "moved"
    folder.rename(moved)
    relinked = restore_workspace(saved, relink=moved, accept_changed=True)
    assert relinked.pipeline.source.source.path == moved
    assert relinked.pipeline.source.table["path"].to_list() == [
        str(moved / "a.png"),
        str(moved / "sub/a.png"),
    ]


def test_empty_folder_nonrecursive_members_and_manifest_validation(
    tmp_path: Path,
) -> None:
    assert load_file(tmp_path).dataset.table.height == 0
    (tmp_path / "sub").mkdir()
    (tmp_path / "sub/a.wav").write_bytes(b"header only")
    assert load_file(tmp_path, MediaOptions(recursive=False)).dataset.table.height == 0
    assert load_file(tmp_path).dataset.table["kind"].to_list() == ["Audio"]
    with pytest.raises(ValueError):
        MediaOptions(manifest=("../escape.png",))
    with pytest.raises(ImportFailure, match="media import options"):
        from datelier.io.types import CsvOptions

        load_file(tmp_path, CsvOptions())


def test_image_folder_routes_to_profiles_without_decoding_mixed_folder(
    tmp_path: Path,
) -> None:
    from datelier.inspection.profile_selection import ProfileSelection

    (tmp_path / "broken.png").write_bytes(b"undecodable")
    images = load_file(tmp_path).dataset
    assert images.role("path").role == ColumnRole.IMAGE
    selection = ProfileSelection(("path",))
    selection.bind(images)
    assert selection.text_column() is None
    assert selection.text_column(prefer_text=True) == "path"
    (tmp_path / "note.txt").write_text("text")
    mixed = load_file(tmp_path).dataset
    assert mixed.role("path").role == ColumnRole.PATH


def test_missing_or_shorter_line_members_keep_other_record_ids(tmp_path: Path) -> None:
    folder = tmp_path / "lines"
    folder.mkdir()
    first = folder / "a.txt"
    first.write_text("one\ntwo\nthree\n")
    second = folder / "b.txt"
    second.write_text("other\n")
    imported = load_file(folder, MediaOptions(text_lines=True))
    assert isinstance(imported.options, MediaOptions)
    assert imported.dataset.table["member"].to_list() == ["a.txt"] * 3 + ["b.txt"]
    first.write_text("one\n")
    restored = load_file(folder, imported.options)
    assert restored.dataset.table["text"].to_list() == ["one", None, None, "other"]
    assert restored.dataset.row_ids.to_list() == [0, 1, 2, 3]
    first.unlink()
    missing = load_file(folder, imported.options)
    assert missing.dataset.table["text"].to_list() == [None, None, None, "other"]
    assert missing.dataset.table["line"].to_list() == [1, 2, 3, 1]
    fresh = load_file(folder, MediaOptions(text_lines=True))
    assert fresh.dataset.table["text"].to_list() == ["other"]


def test_changed_media_session_keeps_selection_on_fixed_manifest(
    tmp_path: Path,
) -> None:
    from datelier.workspace.sessions import SessionFile
    from datelier.workspace.sessions.restore import SourceRecovery, restore_session_file

    folder = tmp_path / "fixed"
    folder.mkdir()
    for name in ("a.png", "b.png"):
        Image.new("RGB", (2, 3)).save(folder / name)
    imported = load_file(folder)
    recipe = Workspace(
        reference_source(imported.dataset.source), imported.format, imported.options
    )
    saved = SessionFile("media", recipe, selection=(1,))
    (folder / "b.png").unlink()
    recovered = restore_session_file(
        saved, SourceRecovery("media", accept_changed=True)
    )
    assert recovered.restored and recovered.file.selection == (1,)
    assert recovered.restored.inspection.dataset.table["member"][1] == "b.png"
    assert recovered.restored.inspection.dataset.table["size_bytes"][1] is None


def test_relinked_line_file_keeps_original_line_identity(tmp_path: Path) -> None:
    source = tmp_path / "old.txt"
    source.write_text("one\ntwo\nthree\n")
    imported = load_file(source, MediaOptions(text_lines=True))
    recipe = Workspace(
        reference_source(imported.dataset.source), imported.format, imported.options
    )
    workspace = tmp_path / "lines.datelier"
    save_workspace(workspace, recipe)
    replacement = tmp_path / "new.txt"
    replacement.write_text("new one\nnew two\n")
    restored = restore_workspace(workspace, relink=replacement, accept_changed=True)
    assert restored.inspection.dataset.row_ids.to_list() == [0, 1, 2]
    assert restored.inspection.dataset.table["line"].to_list() == [1, 2, 3]
    assert restored.inspection.dataset.table["text"].to_list() == [
        "new one",
        "new two",
        None,
    ]
    assert restored.inspection.dataset.table["path"].to_list() == [str(replacement)] * 3


def test_exports_and_workspace_writes_preserve_collection_members_and_aliases(
    tmp_path: Path,
) -> None:
    from datelier.io.exporting import ExportFailure, ExportFormat, export_dataset

    folder = tmp_path / "protected"
    folder.mkdir()
    image = folder / "source.png"
    Image.new("RGB", (4, 3)).save(image)
    outside = tmp_path / "outside.bin"
    outside.write_bytes(b"original asset")
    (folder / "alias.png").symlink_to(outside)
    hardlink = tmp_path / "hardlink.bin"
    hardlink.hardlink_to(image)
    imported = load_file(folder)
    original = image.read_bytes()
    with pytest.raises(ExportFailure, match="preserved"):
        export_dataset(imported.dataset, image, ExportFormat.CSV, overwrite=True)
    with pytest.raises(ExportFailure, match="preserved"):
        export_dataset(imported.dataset, outside, ExportFormat.CSV, overwrite=True)
    with pytest.raises(ExportFailure, match="preserved"):
        export_dataset(imported.dataset, hardlink, ExportFormat.CSV, overwrite=True)
    recipe = Workspace(
        reference_source(imported.dataset.source), imported.format, imported.options
    )
    with pytest.raises(ValueError, match="source data"):
        save_workspace(image, recipe)
    assert image.read_bytes() == original and outside.read_bytes() == b"original asset"
    destination = folder / "metadata.csv"
    assert export_dataset(imported.dataset, destination, ExportFormat.CSV).rows == 2
    save_workspace(folder / "session.datelier", recipe)
    assert restore_workspace(folder / "session.datelier").inspection.row_count == 2
