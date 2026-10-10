"""Whole-session recipes, legacy migration, partial recovery and atomic integrity."""

import json
from dataclasses import replace
from pathlib import Path

import pytest

from datelier.analysis.types import AnalysisRequest, PCAParameters
from datelier.inspection.comparison_settings import (
    ComparisonSettings,
    ComparisonSource,
    Normalization,
)
from datelier.inspection.exploration import PlotSettings
from datelier.io.importing import load_file
from datelier.io.types import CsvOptions, ImportFormat
from datelier.pipeline.operations import Sort
from datelier.workspace.session_restore import (
    SourceRecovery,
    restore_session_file,
    restore_session_workspace,
)
from datelier.workspace.session_storage import (
    read_session_workspace,
    save_session_workspace,
)
from datelier.workspace.session_types import SessionFile, SessionWorkspace, SourceDraft
from datelier.workspace.storage import reference_source, save_workspace
from datelier.workspace.types import Workspace, WorkspaceViews


def fixture(tmp_path: Path) -> SessionWorkspace:
    train, test = tmp_path / "train.csv", tmp_path / "test.csv"
    train.write_text("x,y\n3,6\n1,2\n2,4\n")
    test.write_text("a;b\n10;20\n30;40\n")
    first = load_file(train)
    second = load_file(test, CsvOptions(separator=";"))
    a = Workspace(
        reference_source(first.dataset.source),
        first.format,
        first.options,
        (Sort(("x",)),),
        1,
        (AnalysisRequest(("x", "y"), PCAParameters(), seed=17),),
        PlotSettings(bins=7),
        WorkspaceViews(target_row=2),
    )
    b = Workspace(
        reference_source(second.dataset.source),
        second.format,
        second.options,
        (Sort(("a",), descending=True),),
        0,
        (AnalysisRequest(("b", "a"), PCAParameters(), seed=29),),
        PlotSettings(bins=13),
    )
    comparison = ComparisonSettings(
        (
            ComparisonSource("train", "x", "Training", (0.1, 0.2, 0.3, 1.0)),
            ComparisonSource("test", "a", "Test"),
        ),
        9,
        12,
        Normalization.COUNT,
    )
    return SessionWorkspace(
        (
            SessionFile("test", b, selection=(0,)),
            SessionFile("welcome"),
            SessionFile(
                "train", a, selection=(1,), panel_scroll=(("Explore", 0.0, 150.0),)
            ),
        ),
        "train",
        (comparison,),
        "[Window][Table preview]\n[Docking][Data]\nDockSpace ID=1\n",
        ("Context",),
    )


def test_round_trip_independent_history_views_mapping_identity_and_selection(
    tmp_path: Path,
) -> None:
    session = fixture(tmp_path)
    path = tmp_path / "session.datelier"
    originals = tuple(
        (tmp_path / name).read_bytes() for name in ("train.csv", "test.csv")
    )
    save_session_workspace(path, session)
    assert read_session_workspace(path) == session
    assert str(tmp_path) not in path.read_text()
    restored = restore_session_workspace(path)
    assert restored.workspace == session
    b, blank, a = restored.files
    assert blank.restored is None and not blank.message
    assert a.restored is not None and b.restored is not None
    assert a.restored.pipeline.current.row_ids.to_list() == [1, 2, 0]
    assert b.restored.pipeline.current.row_ids.to_list() == [0, 1]
    assert b.restored.pipeline.can_redo and a.restored.pipeline.can_undo
    assert (
        a.restored.pipeline.current.revision.dataset_id
        != b.restored.pipeline.current.revision.dataset_id
    )
    assert a.file.selection == (1,) and b.file.selection == (0,)
    assert a.file.recipe is not None and a.file.recipe.analysis[0].seed == 17
    assert b.file.recipe is not None and b.file.recipe.analysis[0].seed == 29
    assert (
        tuple((tmp_path / name).read_bytes() for name in ("train.csv", "test.csv"))
        == originals
    )


def test_legacy_workspace_migrates_to_one_file_and_resaves_as_version_three(
    tmp_path: Path,
) -> None:
    session = fixture(tmp_path)
    recipe = session.files[2].recipe
    assert recipe is not None
    legacy = tmp_path / "legacy.datelier"
    save_workspace(legacy, recipe)
    migrated = read_session_workspace(legacy)
    assert migrated.version == 3 and migrated.active_id == "legacy-source"
    assert migrated.files == (SessionFile("legacy-source", recipe),)
    saved = tmp_path / "new.datelier"
    save_session_workspace(saved, migrated)
    assert json.loads(saved.read_text())["version"] == 3
    assert restore_session_workspace(saved).files[0].restored is not None


def test_missing_changed_and_bad_sources_are_independently_recoverable(
    tmp_path: Path,
) -> None:
    session = fixture(tmp_path)
    malformed = tmp_path / "bad.csv"
    malformed.write_text('x,y\n"unclosed,2\n')
    draft = SessionFile(
        "failed", draft=SourceDraft(str(malformed), ImportFormat.CSV, CsvOptions())
    )
    session = replace(session, files=(*session.files, draft))
    path = tmp_path / "session.datelier"
    save_session_workspace(path, session)
    train, moved = tmp_path / "train.csv", tmp_path / "moved.csv"
    train.rename(moved)
    restored = restore_session_workspace(path)
    assert restored.files[0].restored is not None
    assert restored.files[2].restored is None and "missing" in restored.files[2].message
    assert (
        restored.files[3].restored is None
        and "replacement source" in restored.files[3].message
    )
    recovered = restore_session_file(
        restored.files[2].file, SourceRecovery("train", moved)
    )
    assert recovered.restored is not None and recovered.file.selection == (1,)
    with pytest.raises(ValueError, match="another file"):
        restore_session_file(restored.files[2].file, SourceRecovery("test", moved))
    moved.write_text("x,y\n30,60\n10,20\n20,40\n")
    changed = restore_session_file(
        restored.files[2].file, SourceRecovery("train", moved)
    )
    assert changed.changed and changed.restored is None and "changed" in changed.message
    accepted = restore_session_file(
        restored.files[2].file, SourceRecovery("train", moved, True)
    )
    assert accepted.restored is not None and accepted.file.selection == ()
    assert accepted.restored.pipeline.current.table["x"].to_list() == [10, 20, 30]
    malformed.write_text("x,y\n5,6\n")
    fixed = restore_session_file(draft)
    assert (
        fixed.restored is not None
        and fixed.file.draft is None
        and fixed.file.recipe is not None
    )
    partial = replace(
        restored.workspace, files=tuple(result.file for result in restored.files)
    )
    save_session_workspace(tmp_path / "partial.datelier", partial)
    assert (
        read_session_workspace(tmp_path / "partial.datelier").files[2]
        == restored.files[2].file
    )


@pytest.mark.parametrize(
    "edit",
    [
        {"active_id": "closed"},
        {"version": True},
        {"version": 4},
        {"unknown": []},
        {"files": []},
        {
            "comparisons": [
                {
                    "kind": "ComparisonSettings",
                    "sources": [
                        {"kind": "ComparisonSource", "file_id": "closed", "column": "x"}
                    ],
                }
            ]
        },
    ],
)
def test_bad_session_topology_is_rejected_before_import(
    tmp_path: Path, edit: dict[str, object], monkeypatch: pytest.MonkeyPatch
) -> None:
    session = fixture(tmp_path)
    path = tmp_path / "session.datelier"
    save_session_workspace(path, session)
    raw = json.loads(path.read_text())
    raw.update(edit)
    path.write_text(json.dumps(raw))
    from datelier.workspace import session_restore

    def forbidden(*args: object, **kwargs: object) -> None:
        raise AssertionError("Invalid session started an import")

    monkeypatch.setattr(session_restore, "restore_recipe", forbidden)
    with pytest.raises(ValueError):
        restore_session_workspace(path)


def test_session_save_is_atomic_and_protects_every_source_and_alias(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from datelier.workspace import storage

    session = fixture(tmp_path)
    path = tmp_path / "session.datelier"
    save_session_workspace(path, session)
    before = path.read_bytes()
    original = Path.replace

    def failed_replace(source: Path, target: Path) -> Path:
        if target == path:
            raise OSError("simulated replacement failure")
        return original(source, target)

    monkeypatch.setattr(Path, "replace", failed_replace)
    with pytest.raises(OSError, match="replacement failure"):
        save_session_workspace(path, replace(session, active_id="test"))
    assert path.read_bytes() == before and not list(
        tmp_path.glob(".session.datelier.*")
    )
    for name in ("train.csv", "test.csv"):
        source = tmp_path / name
        alias = tmp_path / f"{name}.json"
        alias.symlink_to(source)
        original_bytes = source.read_bytes()
        with pytest.raises(ValueError, match="source data"):
            save_session_workspace(alias, session)
        assert source.read_bytes() == original_bytes
    assert storage.MAX_WORKSPACE_BYTES == 2 * 1024 * 1024


def test_session_sources_can_move_with_workspace_and_stale_selection_is_pruned(
    tmp_path: Path,
) -> None:
    root = tmp_path / "original"
    root.mkdir()
    session = fixture(root)
    first = session.files[2]
    assert first.recipe is not None
    # IDs remain tied to their file, and unavailable rows never become display offsets.
    session = replace(
        session, files=(*session.files[:2], replace(first, selection=(1, 500)))
    )
    save_session_workspace(root / "session.datelier", session)
    moved = tmp_path / "moved"
    root.rename(moved)
    restored = restore_session_workspace(moved / "session.datelier")
    assert restored.files[2].restored is not None and restored.files[
        2
    ].file.selection == (1,)
    assert "Selection adjusted" in restored.files[2].message
    assert restored.workspace.comparisons == session.comparisons


def test_oversized_session_and_duplicate_recoveries_leave_previous_recipe_usable(
    tmp_path: Path,
) -> None:
    from datelier.workspace.storage import MAX_WORKSPACE_BYTES

    session = fixture(tmp_path)
    path = tmp_path / "session.datelier"
    save_session_workspace(path, session)
    before = path.read_bytes()
    source = replace(session.comparisons[0].sources[0], label="x" * MAX_WORKSPACE_BYTES)
    comparison = replace(session.comparisons[0], sources=(source,))
    with pytest.raises(ValueError, match="2 MiB"):
        save_session_workspace(path, replace(session, comparisons=(comparison,)))
    assert path.read_bytes() == before
    with pytest.raises(ValueError, match="distinct saved"):
        restore_session_workspace(
            path, recoveries=(SourceRecovery("test"), SourceRecovery("test"))
        )
    with pytest.raises(ValueError, match="distinct saved"):
        restore_session_workspace(path, recoveries=(SourceRecovery("closed"),))
    assert restore_session_workspace(path).files[0].restored is not None


def test_version_two_migration_preserves_recipes_and_resets_only_old_layout(
    tmp_path: Path,
) -> None:
    from datelier.workspace.session_storage import read_session_with_notice

    session = fixture(tmp_path)
    path = tmp_path / "old.datelier"
    save_session_workspace(path, session)
    raw = json.loads(path.read_text())
    raw["version"] = 2
    raw["layout"] = (
        "[Window][Analysis]\n[Window][Table preview]\n[Docking][Data]\nDockSpace ID=1\n"
    )
    raw["hidden_windows"] = ["Analysis", "Explore"]
    for key in ("layout_version", "canvas_mode", "context_tab", "custom_layout"):
        raw.pop(key)
    path.write_text(json.dumps(raw))
    migrated, notice = read_session_with_notice(path)
    assert migrated == replace(session, layout="", hidden_windows=())
    assert "layout updated" in notice
    reopened = restore_session_workspace(path)
    assert reopened.notice == notice
    assert reopened.files[2].restored is not None
    assert reopened.files[2].restored.pipeline.current.row_ids.to_list() == [1, 2, 0]


def test_new_canvas_context_and_content_sizes_round_trip(tmp_path: Path) -> None:
    session = fixture(tmp_path)
    first = session.files[0]
    assert first.recipe is not None
    first = replace(
        first,
        recipe=replace(
            first.recipe,
            views=replace(
                first.recipe.views, image_height=350, text_height=220, token_height=300
            ),
        ),
    )
    session = replace(
        session,
        files=(first, *session.files[1:]),
        canvas_mode="Compare files",
        context_tab="History",
        custom_layout=True,
    )
    path = tmp_path / "new.datelier"
    save_session_workspace(path, session)
    assert read_session_workspace(path) == session
    raw = json.loads(path.read_text())
    assert raw["version"] == 3 and raw["layout_version"] == 2


@pytest.mark.parametrize("height", [float("nan"), float("inf"), -1, 99])
def test_invalid_content_size_is_rejected(height: float) -> None:
    with pytest.raises(ValueError, match="Content heights"):
        WorkspaceViews(image_height=height).validate()
