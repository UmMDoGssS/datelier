from pathlib import Path

import pytest
from PIL import Image

from datelier.core.column_roles import ColumnRole
from datelier.io.importing import load_file
from datelier.io.types import ImportFailure, ImportFormat, MediaOptions
from datelier.pipeline.history import Pipeline
from datelier.pipeline.operations import Sort
from datelier.workspace.restore import SourceIssue, restore_workspace
from datelier.workspace.storage import reference_source, save_workspace
from datelier.workspace.types import Workspace


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
    assert imported.dataset.role("path").role == ColumnRole.PATH
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
