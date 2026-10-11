from collections.abc import Callable
from pathlib import Path
from threading import Event
from time import monotonic, sleep
from types import ModuleType
from uuid import uuid4

import numpy as np
import pytest

from datelier.application.sessions import EditorController
from datelier.application.sessions.workspace import capture_session
from datelier.core import DatasetRevision, SharedWorkers
from datelier.inspection.arrays.settings import SliceSettings
from datelier.inspection.checkpoints import CheckpointCatalog
from datelier.inspection.checkpoints.jobs import CheckpointJobs
from datelier.inspection.checkpoints.slices import PreparedTensorSlice
from datelier.io.checkpoints.storage import CheckpointStore
from datelier.io.importing import load_file
from datelier.io.jobs import LoadPhase
from datelier.workspace.sessions.jobs import save_snapshot


@pytest.fixture
def torch() -> ModuleType:
    return pytest.importorskip("torch")


def wait(editor: EditorController) -> None:
    deadline = monotonic() + 6
    while monotonic() < deadline:
        editor.poll()
        if not editor.workspace.busy and all(
            f.loader.status.phase != LoadPhase.LOADING and not f.checkpoints.busy
            for f in editor.all_files
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
    editor = EditorController()
    try:
        file = editor.new_file(source)
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
    reopened = EditorController()
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
    editor = EditorController()
    try:
        one, two = editor.new_file(first), editor.new_file(second)
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
    reopened = EditorController()
    try:
        reopened.open_workspace(workspace)
        wait(reopened)
        one = next(f for f in reopened.files if f.identity == one_id)
        assert one.recovery and reopened.active.loader.active
        reopened.recover(one_id, replacement, False)
        wait(reopened)
        assert one.recovery is None and one.checkpoints.catalog
        assert one.checkpoints.catalog.source.path == replacement
        assert one.checkpoints.active is None and one.checkpoints.store.loads == 0
    finally:
        reopened.close()


def test_checkpoint_controller_closes_after_external_worker_shutdown(
    tmp_path: Path, torch: ModuleType
) -> None:
    source = tmp_path / "cached.pt"
    torch.save(torch.arange(3), source)
    catalog = load_file(source).checkpoint_catalog
    assert catalog
    workers = SharedWorkers()
    jobs = CheckpointJobs(workers)
    jobs.bind(catalog, DatasetRevision(uuid4()))
    jobs.request(SliceSettings("$", (0,), (0,), (0,), (3,)))
    deadline = monotonic() + 3
    while jobs.busy and monotonic() < deadline:
        jobs.poll()
        sleep(0.001)
    assert jobs.active and jobs.store.stored_bytes > 0
    workers.shutdown()
    jobs.close()
    assert jobs.closed and jobs.store.stored_bytes == 0


def test_changed_checkpoint_requires_acceptance_and_recovers_metadata_only(
    tmp_path: Path, torch: ModuleType
) -> None:
    source = tmp_path / "changed.pt"
    torch.save({"weight": torch.arange(6).reshape(2, 3)}, source)
    workspace = tmp_path / "changed.datelier"
    editor = EditorController()
    try:
        file = editor.new_file(source)
        wait(editor)
        file.checkpoints.settings = SliceSettings(
            "$['weight']", (0, 1), (0, 0), (0, 0), (128, 128)
        )
        identity = file.identity
        save_snapshot(workspace, capture_session(editor), False)
    finally:
        editor.close()
    torch.save({"weight": torch.tensor([8, 9, 10])}, source)
    reopened = EditorController()
    try:
        reopened.open_workspace(workspace)
        wait(reopened)
        file = next(f for f in reopened.files if f.identity == identity)
        assert file.recovery and file.recovery.changed
        reopened.recover(identity, None, True)
        wait(reopened)
        assert file.recovery is None and file.checkpoints.catalog
        assert file.checkpoints.catalog.tensor("$['weight']").shape == (3,)
        assert file.checkpoints.active is None and file.checkpoints.store.loads == 0
        file.checkpoints.request(SliceSettings("$['weight']", (0,), (0,), (0,), (3,)))
        wait(reopened)
        assert file.checkpoints.active
        assert file.checkpoints.active.view.raw.tolist() == [8, 9, 10]
    finally:
        reopened.close()
