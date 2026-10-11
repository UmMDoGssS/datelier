"""Mixed recipes, shared-array ownership, atomic failure and idle recovery."""

from collections.abc import Callable
from dataclasses import replace
from pathlib import Path
from time import monotonic, sleep
from unittest.mock import patch

from audio_playback_fixtures import Devices

from datelier.application.editor import EditorController
from datelier.application.file import FileController
from datelier.application.workspace import capture_session, install_file
from datelier.feasibility.multimodal import make_multimodal
from datelier.inspection.arrays.mapping import (
    ArrayLayout,
    ArrayRecordMapping,
    SupportingArray,
)
from datelier.inspection.audio.playback.controller import PlaybackPhase
from datelier.inspection.audio.types import AudioRange
from datelier.inspection.images.types import ImageDisplay, ImageWindow
from datelier.inspection.references.types import ReferenceSettings
from datelier.inspection.text.types import CorpusMode, TextScope
from datelier.io.loading import LoadPhase
from datelier.io.types import ArrayOptions
from datelier.pipeline.operations import Sort
from datelier.pipeline.types import CastColumn, TargetType
from datelier.workspace.session_jobs import save_snapshot
from datelier.workspace.session_restore import restore_session_workspace
from datelier.workspace.storage import save_workspace


def until(editor: EditorController, ready: Callable[[], bool]) -> None:
    deadline = monotonic() + 5
    while monotonic() < deadline:
        editor.poll()
        if ready():
            return
        sleep(0.001)
    raise AssertionError("Mixed session did not settle")


def settle(editor: EditorController, root: Path) -> None:
    def ready() -> bool:
        for file in editor.all_files:
            if (
                file.loader.active is not None
                and file.loader.active.imported.array_catalog is None
                and file.references.settings.roots != (str(root),)
            ):
                file.references.configure(ReferenceSettings(roots=(str(root),)))
                return False
        return not editor.workspace.busy and all(
            f.loader.status.phase != LoadPhase.LOADING
            and not f.editor.busy
            and not f.record_views.pending
            and not f.references.busy
            and not f.audio.jobs.busy
            and not f.images.jobs.busy
            and not f.text.jobs.busy
            for f in editor.all_files
        )

    until(editor, ready)


def mapped(
    editor: EditorController, owner: FileController, member: str, layout: ArrayLayout
) -> FileController:
    mapping = ArrayRecordMapping(
        member,
        layout=layout,
        display_axes=(1, 2) if layout == ArrayLayout.IMAGE else (1,),
        channel_axis=3 if layout == ArrayLayout.IMAGE else 2,
        supporting=(
            SupportingArray("labels", "label"),
            SupportingArray("captions", "caption"),
        ),
    )
    view = owner.record_views.open_array(owner, mapping)
    until(editor, lambda: view.loader.active is not None)
    view.editor.request(Sort(("label",)))
    settle(
        editor,
        owner.loader.active.dataset.source.path.parent
        if owner.loader.active
        else Path.cwd(),
    )
    return view


def audio_record(editor: EditorController, file: FileController, column: str) -> None:
    assert file.loader.active is not None
    active = file.loader.active
    options = active.imported.options
    file.audio.jobs.request_record(
        active.dataset,
        column,
        0,
        active.imported.array_catalog,
        options.mapping if isinstance(options, ArrayOptions) else None,
        file.audio.settings.array_sample_rate,
    )
    until(editor, lambda: file.audio.jobs.metadata is not None)


def test_mixed_mapped_views_keep_support_and_shared_cache_after_one_closes(
    tmp_path: Path,
) -> None:
    fixtures = make_multimodal(tmp_path)
    originals = {p: p.read_bytes() for p in fixtures.sources}
    devices = Devices()
    editor = EditorController(playback_factory=devices.create)
    try:
        csv = editor.new_file(fixtures.train)
        owner = editor.new_file(fixtures.arrays)
        settle(editor, tmp_path)
        image = mapped(editor, owner, "images", ArrayLayout.IMAGE)
        audio = mapped(editor, owner, "audio", ArrayLayout.AUDIO)
        owner.arrays.set_retention(1)
        assert image.arrays.store is audio.arrays.store is owner.arrays.store
        assert image.loader.active and audio.loader.active
        image_options = image.loader.active.imported.options
        assert isinstance(image_options, ArrayOptions)
        assert (
            image.loader.active.dataset.row_ids.to_list()
            == audio.loader.active.dataset.row_ids.to_list()
            == [1, 2, 0]
        )
        image.images.jobs.request_record(
            image.loader.active.dataset,
            "images",
            0,
            image.arrays.catalog,
            image_options.mapping,
        )
        settle(editor, tmp_path)
        assert image.images.jobs.metadata is not None
        image.images.jobs.request_window(
            ImageWindow(width=16, height=12), ImageDisplay(), image.arrays.store
        )
        image.text.jobs.settings = replace(
            image.text.jobs.settings,
            column="caption",
            scope=TextScope(CorpusMode.COLLECTION),
        )
        editor.poll()
        image.text.jobs.request_document()
        settle(editor, tmp_path)
        assert image.images.jobs.active and image.images.jobs.active.pixel(0, 0) == (
            80,
            20,
            30,
        )
        assert (
            image.text.jobs.active
            and image.text.jobs.active.document.origin.row_id == 1
        )
        assert image.text.jobs.active.document.text == "array b e\u0301"
        audio.audio.settings = replace(audio.audio.settings, array_sample_rate=8000)
        audio_record(editor, audio, "audio")
        audio.audio.jobs.request_window(AudioRange(0, 32), audio.arrays.store)
        settle(editor, tmp_path)
        assert (
            audio.audio.jobs.active
            and audio.audio.jobs.active.locator.origin.row_id == 1
        )
        assert audio.audio.jobs.active.raw.dtype.name == "float32"
        assert owner.arrays.store.stored_bytes == 0
        editor.activate(csv.identity)
        audio_record(editor, csv, "audio")
        assert csv.audio.jobs.metadata is not None
        csv.audio.play()
        until(editor, lambda: editor.playback.snapshot.phase == PlaybackPhase.PLAYING)
        owner.record_views.close_view(image.identity)
        assert image.closed and not owner.arrays.store.stop.is_set()
        assert editor.playback.snapshot.phase == PlaybackPhase.PLAYING
        audio.audio.jobs.request_profile(
            AudioRange(), audio.audio.settings.thresholds, audio.arrays.store
        )
        settle(editor, tmp_path)
        assert (
            audio.audio.jobs.profile
            and audio.audio.jobs.profile.locator.origin.row_id == 1
        )
        assert editor.playback.snapshot.phase == PlaybackPhase.PLAYING
        assert csv.loader.active and csv.editor.pipeline
        revision, history = csv.loader.revision, csv.editor.pipeline.history
        csv.editor.request(CastColumn("caption", TargetType.INT))
        settle(editor, tmp_path)
        assert (
            csv.loader.revision == revision and csv.editor.pipeline.history == history
        )
        assert csv.editor.message.startswith("Edit failed:")
        assert editor.playback.snapshot.phase == PlaybackPhase.PLAYING
        editor.close_file(csv.identity)
        until(editor, lambda: editor.playback.snapshot.phase == PlaybackPhase.IDLE)
        assert devices.devices[-1].closed
        editor.close_file(owner.identity)
        assert owner.arrays.store.stop.is_set()
    finally:
        editor.close()
    assert all(p.read_bytes() == original for p, original in originals.items())


def test_mixed_session_restores_idle_recovers_manifest_and_migrates_legacy(
    tmp_path: Path,
) -> None:
    fixtures = make_multimodal(tmp_path)
    workspace = tmp_path / "mixed.datelier"
    editor = EditorController()
    try:
        train = editor.new_file(fixtures.train)
        test = editor.new_file(fixtures.test)
        owner = editor.new_file(fixtures.arrays)
        owner.loader.request(fixtures.arrays, ArrayOptions(record_table=False))
        settle(editor, tmp_path)
        image = mapped(editor, owner, "images", ArrayLayout.IMAGE)
        audio = mapped(editor, owner, "audio", ArrayLayout.AUDIO)
        audio.audio.settings = replace(audio.audio.settings, array_sample_rate=8000)
        train.text.jobs.settings = replace(train.text.jobs.settings, column="caption")
        assert train.loader.revision is not None
        train.selection.choose(train.loader.revision, (1,))
        editor.activate(test.identity)
        snapshot = capture_session(editor)
        save_snapshot(workspace, snapshot, False)
        train_id, owner_id, image_id, audio_id = (
            train.identity,
            owner.identity,
            image.identity,
            audio.identity,
        )
    finally:
        editor.close()
    fixtures.train.rename(tmp_path / "moved.csv")
    reopened = EditorController()
    try:
        with (
            patch(
                "datelier.io.arrays.storage.ArrayStore.open_member",
                side_effect=AssertionError("Restore decoded payload"),
            ),
            patch(
                "datelier.inspection.audio.comparisons.jobs.prepare_comparison",
                side_effect=AssertionError("Restore profiled audio"),
            ),
        ):
            reopened.open_workspace(workspace)
            settle(reopened, tmp_path)
        files = {f.identity: f for f in reopened.all_files}
        assert files[train_id].recovery and files[owner_id].loader.active
        image_recovery, audio_recovery = (
            files[image_id].recovery,
            files[audio_id].recovery,
        )
        assert image_recovery is not None and image_recovery.deferred
        assert audio_recovery is not None and audio_recovery.deferred
        assert not any(
            f.audio.jobs.active
            or f.audio.jobs.profile
            or f.images.jobs.active
            or f.text.jobs.active
            for f in reopened.all_files
        )
        assert (
            reopened.playback.snapshot.request is None
            and not reopened.playback.devices.busy
        )
        assert (
            not reopened.compare.text.jobs.busy
            and not reopened.compare.images.jobs.busy
            and not reopened.compare.audio.jobs.busy
        )
        reopened.recover(train_id, tmp_path / "moved.csv", False)
        settle(reopened, tmp_path)
        assert files[train_id].loader.active and files[train_id].selection.row_ids == {
            1
        }
        reopened.recover(audio_id, None, False, True)
        settle(reopened, tmp_path)
        restored_audio = files[audio_id].loader.active
        image_recovery = files[image_id].recovery
        assert restored_audio and image_recovery is not None and image_recovery.deferred
        assert restored_audio.dataset.row_ids.to_list() == [1, 2, 0]
        assert files[audio_id].audio.settings.array_sample_rate == 8000
        recipe = capture_session(reopened).workspace.files[1].recipe
        assert recipe is not None
        legacy = tmp_path / "legacy.datelier"
        save_workspace(legacy, recipe)
        reopened.open_workspace(legacy)
        settle(reopened, tmp_path)
        assert len(reopened.files) == 1 and reopened.active.identity == "legacy-source"
        assert reopened.playback.snapshot.request is None
    finally:
        reopened.close()


def test_restored_catalog_inspect_is_bound_before_its_first_frame(
    tmp_path: Path,
) -> None:
    fixtures = make_multimodal(tmp_path)
    workspace = tmp_path / "stale-inspect.datelier"
    editor = EditorController()
    try:
        owner = editor.new_file()
        owner.open(fixtures.arrays, ArrayOptions(record_table=False))
        settle(editor, tmp_path)
        owner.records.settings = replace(
            owner.records.settings,
            primary="audio",
            supporting=("caption", "label"),
            gallery=False,
        )
        save_snapshot(workspace, capture_session(editor), False)
    finally:
        editor.close()
    restored = restore_session_workspace(workspace)
    reopened = EditorController()
    try:
        file = reopened.active
        install_file(
            file, next(f for f in restored.files if f.file.identity == owner.identity)
        )
        # The GUI renders immediately after installation, before FileController.poll.
        assert file.loader.active is not None
        dataset = file.loader.active.dataset
        assert file.records.settings.primary in dataset.table.columns
        assert dataset.role(file.records.settings.primary or "").name
        assert file.records.settings.supporting == ()
        assert not file.records.settings.gallery
        assert file.records.jobs.active is None
        assert file.arrays.store.extractions == 0
    finally:
        reopened.close()
