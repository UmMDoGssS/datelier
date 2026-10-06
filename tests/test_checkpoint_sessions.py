from collections.abc import Callable
from pathlib import Path
from threading import Event
from time import monotonic, sleep
from types import ModuleType
from uuid import uuid4

import numpy as np
import pytest

from datelier.core.dataset import DatasetRevision
from datelier.gui.editor_session import EditorSession
from datelier.gui.workspace.capture import capture_session
from datelier.inspection.arrays.settings import SliceSettings
from datelier.inspection.checkpoints.jobs import CheckpointJobs
from datelier.inspection.checkpoints.slices import PreparedTensorSlice
from datelier.inspection.checkpoints.types import CheckpointCatalog
from datelier.io.checkpoints.storage import CheckpointStore
from datelier.io.importing import load_file
from datelier.io.loading import LoadPhase
from datelier.workspace.session_jobs import save_snapshot


@pytest.fixture
def torch() -> ModuleType:
    return pytest.importorskip("torch")


def wait(editor: EditorSession) -> None:
    deadline = monotonic() + 6
    while monotonic() < deadline:
        editor.poll()
        if not editor.workspace_jobs.busy and all(
            f.loader.status.phase != LoadPhase.LOADING and not f.checkpoints.busy
            for f in editor.file_sessions
        ):
            return
        sleep(0.001)
    raise AssertionError("Checkpoint session did not complete")


def test_checkpoint_workspace_reopens_locators_and_settings_without_values(
    tmp_path: Path, torch: ModuleType, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "nested.pt"
    torch.save(
        {"model": {"weight": torch.arange(24).reshape(2, 3, 4)}, "epoch": 7}, source
    )
    before = source.read_bytes()
    workspace = tmp_path / "checkpoint.datelier"
    editor = EditorSession()
    try:
        file = editor.new_tab(source)
        wait(editor)
        assert file.checkpoints.catalog and file.checkpoints.active is None
        assert file.checkpoints.store.loads == 0
        settings = SliceSettings(
            "$['model']['weight']", (2, 1), (1, 0, 0), (1, 0), (2, 3)
        )
        file.checkpoints.settings = settings
        file.checkpoints.store.limit = 123456
        file.record_views.path = ("model", "weight")
        file.record_views.expanded = {(), ("model",)}
        save_snapshot(workspace, capture_session(editor), False)
        file.checkpoints.request(settings)
        wait(editor)
        assert file.checkpoints.active
        np.testing.assert_array_equal(
            file.checkpoints.active.view.raw,
            np.arange(24).reshape(2, 3, 4)[1, :, 1:3].T,
        )
        store = file.checkpoints.store
    finally:
        editor.close()
    assert store.stored_bytes == 0
    original_open = CheckpointStore.open_tensor

    def forbidden(*args: object, **kwargs: object) -> object:
        raise AssertionError("Workspace reopening must not open tensor storage")

    monkeypatch.setattr(CheckpointStore, "open_tensor", forbidden)
    reopened = EditorSession()
    try:
        reopened.open_workspace(workspace)
        wait(reopened)
        file = reopened.active
        assert file.checkpoints.settings == settings
        assert file.checkpoints.store.limit == 123456
        assert file.record_views.path == ("model", "weight")
        assert file.checkpoints.active is None and file.checkpoints.store.loads == 0
        assert not file.analysis.jobs.results
        save_snapshot(tmp_path / "resaved.datelier", capture_session(reopened), False)
        monkeypatch.setattr(CheckpointStore, "open_tensor", original_open)
        file.checkpoints.request(file.checkpoints.settings)
        wait(reopened)
        assert file.checkpoints.active
        assert file.checkpoints.active.view.raw.shape == (2, 3)
        assert source.read_bytes() == before
        with pytest.raises(ValueError, match="source"):
            save_snapshot(source, capture_session(reopened), True)
    finally:
        reopened.close()


def test_checkpoint_jobs_reject_old_revision_and_closed_owner_results(
    tmp_path: Path, torch: ModuleType, monkeypatch: pytest.MonkeyPatch
) -> None:
    import datelier.inspection.checkpoints.jobs as module

    source = tmp_path / "data.pt"
    torch.save(torch.arange(10), source)
    catalog = load_file(source).checkpoint_catalog
    assert catalog
    started, release = Event(), Event()
    original = module.prepare_tensor_slice

    def controlled(
        store: CheckpointStore,
        catalog: CheckpointCatalog,
        settings: SliceSettings,
        cancelled: Callable[[], bool] | None = None,
    ) -> PreparedTensorSlice:
        if settings.starts == (0,):
            started.set()
            assert release.wait(5)
        return original(store, catalog, settings, cancelled)

    monkeypatch.setattr(module, "prepare_tensor_slice", controlled)
    jobs = CheckpointJobs()
    try:
        jobs.bind(catalog, DatasetRevision(uuid4()))
        jobs.request(SliceSettings(starts=(0,), counts=(2,)))
        assert started.wait(2)
        jobs.bind(catalog, DatasetRevision(uuid4()))
        jobs.request(SliceSettings(starts=(5,), counts=(2,)))
        release.set()
        deadline = monotonic() + 3
        while jobs.busy and monotonic() < deadline:
            jobs.poll()
            sleep(0.001)
        assert jobs.active and jobs.active.view.raw.tolist() == [5, 6]
        jobs.close()
        jobs.poll()
        assert jobs.active is None and jobs.catalog is None
    finally:
        release.set()
        if not jobs.closed:
            jobs.close()


def test_checkpoint_tabs_namespace_same_tensor_and_restore_missing_source_locally(
    tmp_path: Path, torch: ModuleType
) -> None:
    first, second = tmp_path / "first.pt", tmp_path / "second.pth"
    torch.save({"weight": torch.tensor([1.0, 2.0])}, first)
    torch.save({"weight": torch.tensor([8.0, 9.0])}, second)
    workspace = tmp_path / "two.datelier"
    editor = EditorSession()
    try:
        one, two = editor.new_tab(first), editor.new_tab(second)
        wait(editor)
        one.checkpoints.request(SliceSettings("$['weight']"))
        two.checkpoints.request(SliceSettings("$['weight']"))
        wait(editor)
        assert one.checkpoints.active and two.checkpoints.active
        assert one.checkpoints.active.view.raw.tolist() == [1, 2]
        assert two.checkpoints.active.view.raw.tolist() == [8, 9]
        assert one.checkpoints.store is not two.checkpoints.store
        one_id = one.identity
        save_snapshot(workspace, capture_session(editor), False)
    finally:
        editor.close()
    replacement = tmp_path / "replacement.pt"
    first.rename(replacement)
    reopened = EditorSession()
    try:
        reopened.open_workspace(workspace)
        wait(reopened)
        one = next(f for f in reopened.files if f.identity == one_id)
        assert one.recovery and reopened.active.loader.active
        reopened.recover_source(one_id, relink=replacement)
        wait(reopened)
        assert one.recovery is None and one.checkpoints.catalog
        assert one.checkpoints.catalog.source.path == replacement
        assert one.checkpoints.active is None and one.checkpoints.store.loads == 0
    finally:
        reopened.close()
