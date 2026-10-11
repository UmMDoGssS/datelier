from collections.abc import Callable
from pathlib import Path
from threading import Event
from time import monotonic, sleep
from uuid import uuid4

import numpy as np
import pytest

from datelier.application.sessions import EditorController
from datelier.application.sessions.workspace import capture_session
from datelier.core import ColumnRole, DatasetRevision
from datelier.inspection.arrays import ArrayCatalog
from datelier.inspection.arrays.jobs import ArrayJobs
from datelier.inspection.arrays.slices import PreparedSlice, SliceSettings
from datelier.io.arrays import ArrayStore
from datelier.io.arrays.metadata import inspect_arrays
from datelier.io.jobs import LoadPhase
from datelier.io.types import ArrayOptions, ImportFormat
from datelier.workspace.sessions.jobs import save_snapshot


def wait(editor: EditorController) -> None:
    deadline = monotonic() + 5
    while monotonic() < deadline:
        editor.poll()
        if not editor.workspace.busy and all(
            f.loader.status.phase != LoadPhase.LOADING and not f.arrays.busy
            for f in editor.files
        ):
            return
        sleep(0.001)
    raise AssertionError("Array session did not finish")


def test_metadata_open_and_workspace_restore_never_prepare_payloads(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "cube.npz"
    np.savez_compressed(
        source, cube=np.arange(60).reshape(3, 4, 5), labels=np.arange(3)
    )
    original = source.read_bytes()
    workspace = tmp_path / "arrays.datelier"

    def forbidden(*args: object, **kwargs: object) -> object:
        raise AssertionError("Opening/restoration must remain metadata only")

    monkeypatch.setattr(np, "memmap", forbidden)
    editor = EditorController()
    try:
        editor.active.loader.request(source, ArrayOptions(record_table=False))
        wait(editor)
        file = editor.active
        assert (
            file.loader.active
            and file.loader.active.imported.format == ImportFormat.ARRAY
        )
        assert file.arrays.catalog and file.arrays.active is None
        assert file.arrays.store.temporary_path is None
        file.arrays.settings = SliceSettings("cube", (2, 0), (0, 2, 0), (1, 0), (3, 2))
        file.arrays.store.limit = 123456
        save_snapshot(workspace, capture_session(editor), False)
    finally:
        editor.close()
    restored = EditorController()
    try:
        restored.open_workspace(workspace)
        wait(restored)
        file = restored.active
        assert file.loader.active and isinstance(
            file.loader.active.imported.options, ArrayOptions
        )
        assert file.arrays.settings.member == "cube" and file.arrays.settings.axes == (
            2,
            0,
        )
        assert file.arrays.settings.fixed == (
            0,
            2,
            0,
        ) and file.arrays.settings.starts == (1, 0)
        assert file.arrays.store.limit == 123456
        assert file.arrays.active is None and file.arrays.store.temporary_path is None
        assert source.read_bytes() == original
    finally:
        restored.close()


def test_explicit_prepare_preserves_values_and_cleans_shared_worker_storage(
    tmp_path: Path,
) -> None:
    path = tmp_path / "data.npz"
    values = np.arange(24).reshape(2, 3, 4)
    np.savez_compressed(path, values=values)
    editor = EditorController()
    try:
        file = editor.new_file(path)
        file.loader.request(path, ArrayOptions(record_table=False))
        wait(editor)
        file.arrays.request(SliceSettings("values", (1, 2), (1, 0, 0)))
        wait(editor)
        assert file.arrays.active
        np.testing.assert_array_equal(file.arrays.active.raw, values[1])
        temporary = file.arrays.store.temporary_path
        assert temporary and temporary.exists()
        editor.close_file(file.identity)
    finally:
        editor.close()
    assert not temporary.exists()


def test_obsolete_array_jobs_do_not_publish_after_revision_switch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import datelier.inspection.arrays.jobs as jobs_module

    path = tmp_path / "data.npy"
    np.save(path, np.arange(10))
    catalog = inspect_arrays(path)
    started, release = Event(), Event()
    original = jobs_module.prepare_slice

    def controlled(
        store: ArrayStore,
        catalog: ArrayCatalog,
        settings: SliceSettings,
        cancelled: Callable[[], bool] | None = None,
    ) -> PreparedSlice:
        if settings.starts == (0,):
            started.set()
            assert release.wait(5)
        return original(store, catalog, settings, cancelled)

    monkeypatch.setattr(jobs_module, "prepare_slice", controlled)
    jobs = ArrayJobs()
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
        assert jobs.active and jobs.active.raw.tolist() == [5, 6]
        jobs.close()
        jobs.poll()
        assert jobs.active is None
    finally:
        release.set()
        if not jobs.closed:
            jobs.close()


def test_member_paths_identify_arrays_without_nearby_reference_decoding(
    tmp_path: Path,
) -> None:
    path = tmp_path / "data.npz"
    np.savez(path, **{"sub/photo.png": np.arange(4)})
    editor = EditorController()
    try:
        file = editor.new_file(path)
        file.loader.request(path, ArrayOptions(record_table=False))
        wait(editor)
        assert file.loader.active
        assert file.loader.active.dataset.role("member").role == ColumnRole.IDENTIFIER
        assert file.references.source is None
        assert file.arrays.active is None and file.arrays.store.temporary_path is None
    finally:
        editor.close()
