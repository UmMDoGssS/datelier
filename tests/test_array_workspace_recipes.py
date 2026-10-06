from dataclasses import replace
from pathlib import Path

import numpy as np
import pytest

from datelier.inspection.arrays.mapping import (
    ArrayLayout,
    ArrayRecordMapping,
    SupportingArray,
)
from datelier.io.arrays.storage import ArrayStore
from datelier.io.importing import load_file
from datelier.io.types import ArrayOptions
from datelier.pipeline.history import Pipeline
from datelier.pipeline.operations import Sort
from datelier.workspace.session_restore import (
    SourceRecovery,
    restore_session_file,
    restore_session_workspace,
)
from datelier.workspace.session_storage import save_session_workspace
from datelier.workspace.session_types import SessionFile, SessionWorkspace
from datelier.workspace.storage import reference_source
from datelier.workspace.types import Workspace


def test_mapped_workspace_opens_metadata_and_prepares_history_only_explicitly(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "records.npz"
    np.savez_compressed(
        source,
        images=np.arange(3 * 4 * 5 * 3).reshape(3, 4, 5, 3),
        labels=np.array([9, 1, 5]),
    )
    original_bytes = source.read_bytes()
    mapping = ArrayRecordMapping(
        "images",
        0,
        ArrayLayout.IMAGE,
        (1, 2),
        3,
        supporting=(SupportingArray("labels", "label"),),
    )
    imported = load_file(source, ArrayOptions(mapping=mapping))
    pipeline = Pipeline.start(imported.dataset).apply(Sort(("label",)))
    root_import = load_file(source)
    reference = reference_source(root_import.dataset.source)
    child = SessionFile(
        "records",
        Workspace(
            reference,
            imported.format,
            imported.options,
            pipeline.history,
            pipeline.cursor,
        ),
        selection=(2,),
        name="images",
    )
    root = SessionFile(
        "source",
        Workspace(reference, root_import.format, root_import.options),
        record_views=(child,),
        active_view="records",
    )
    workspace = tmp_path / "arrays.datelier"
    save_session_workspace(workspace, SessionWorkspace((root,), "source"))
    original_open = ArrayStore.open_member

    def forbidden(*args: object, **kwargs: object) -> object:
        raise AssertionError("Workspace restore must not open array payloads")

    monkeypatch.setattr(ArrayStore, "open_member", forbidden)
    restored = restore_session_workspace(workspace)
    owner = restored.files[0]
    assert owner.restored is not None
    assert len(owner.record_views) == 1
    view = owner.record_views[0]
    assert view.deferred and view.restored is None and view.array_catalog is not None
    assert view.array_catalog is owner.restored.inspection.imported.array_catalog
    assert view.file.recipe and view.file.recipe.options == imported.options
    assert view.file.recipe.history == pipeline.history and view.file.selection == (2,)
    monkeypatch.setattr(ArrayStore, "open_member", original_open)
    prepared = restore_session_file(
        view.file, SourceRecovery("records", prepare_records=True)
    )
    assert prepared.restored and not prepared.deferred
    assert prepared.restored.inspection.dataset.row_ids.to_list() == [1, 2, 0]
    assert prepared.restored.inspection.dataset.table["label"].to_list() == [1, 5, 9]
    assert prepared.file.selection == (2,)
    assert source.read_bytes() == original_bytes


def test_changed_array_mapping_retains_metadata_with_reset_selection_and_local_mismatch(
    tmp_path: Path,
) -> None:
    source = tmp_path / "records.npz"
    np.savez(source, images=np.zeros((3, 4, 5)), labels=np.arange(3))
    mapping = ArrayRecordMapping(
        "images",
        0,
        ArrayLayout.HEATMAP,
        (1, 2),
        supporting=(SupportingArray("labels", "label"),),
    )
    imported = load_file(source, ArrayOptions(mapping=mapping))
    file = SessionFile(
        "records",
        Workspace(
            reference_source(imported.dataset.source), imported.format, imported.options
        ),
        selection=(2,),
    )
    np.savez(source, images=np.zeros((3, 4, 5)), labels=np.array([7, 8, 9]))
    issue = restore_session_file(file)
    assert issue.changed and not issue.deferred
    accepted = restore_session_file(
        file, SourceRecovery("records", accept_changed=True)
    )
    assert accepted.deferred and accepted.file.selection == ()
    np.savez(source, images=np.zeros((2, 4, 5)), labels=np.arange(3))
    issue = restore_session_file(file, SourceRecovery("records", accept_changed=True))
    assert not issue.deferred and issue.restored is None
    assert "without truncation" in issue.message


def test_mapped_views_relink_as_recipe_references_and_cannot_overwrite_source(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source.npy"
    np.save(source, np.zeros((2, 4, 5)))
    mapping = ArrayRecordMapping("$", 0, ArrayLayout.HEATMAP, (1, 2))
    imported = load_file(source, ArrayOptions(mapping=mapping))
    reference = reference_source(imported.dataset.source)
    view = SessionFile(
        "records", Workspace(reference, imported.format, imported.options), name="array"
    )
    meta = load_file(source)
    root = SessionFile(
        "source",
        Workspace(reference, meta.format, meta.options),
        record_views=(view,),
        active_view="records",
    )
    recipe = SessionWorkspace((root,), "source")
    with pytest.raises(ValueError, match="source"):
        save_session_workspace(source, recipe)
    replacement = tmp_path / "renamed.npy"
    source.rename(replacement)
    restored = restore_session_file(root, SourceRecovery("source", relink=replacement))
    assert restored.restored and restored.record_views[0].deferred
    assert restored.record_views[0].file.recipe
    assert restored.record_views[0].file.recipe.source.path == str(replacement)
    updated = replace(recipe, files=(restored.file,))
    save_session_workspace(tmp_path / "relinked.datelier", updated)
