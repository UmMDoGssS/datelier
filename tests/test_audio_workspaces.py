"""Independent audio recipes restore without decoded or profiled signals."""

from dataclasses import replace
from pathlib import Path
from time import monotonic, sleep

import numpy as np
import pytest
import soundfile as sf

from datelier.core.column_roles import ColumnRole
from datelier.gui.editor_session import EditorSession
from datelier.gui.workspace.capture import capture_session
from datelier.inspection.audio.profile_types import AudioThresholds
from datelier.inspection.audio.settings import AudioSettings
from datelier.inspection.audio.types import AudioRange
from datelier.workspace.codec import decode_record, encode
from datelier.workspace.session_jobs import save_snapshot
from datelier.workspace.types import WorkspaceViews


def wait(editor: EditorSession) -> None:
    deadline = monotonic() + 5
    while monotonic() < deadline:
        editor.poll()
        if not editor.workspace_jobs.busy and all(
            (not file.controls.path or file.loader.active is not None)
            and not file.references.busy
            and not file.audio.jobs.busy
            for file in editor.file_sessions
        ):
            return
        sleep(0.001)
    raise AssertionError("Audio session work did not finish")


def test_audio_settings_and_legacy_workspace_defaults() -> None:
    settings = AudioSettings(
        22050, AudioRange(200, 300), AudioThresholds(0.75, 0.01), 1, 1024 * 1024
    )
    settings.validate()
    views = replace(WorkspaceViews(), audio=settings)
    assert decode_record(WorkspaceViews, encode(views)) == views
    legacy = encode(WorkspaceViews())
    assert isinstance(legacy, dict)
    del legacy["audio"]
    assert decode_record(WorkspaceViews, legacy).audio == AudioSettings()
    for invalid in (
        replace(settings, array_sample_rate=0),
        replace(settings, channel=-1),
        replace(settings, cpu_bytes=0),
        replace(settings, range=AudioRange(4, 1)),
    ):
        with pytest.raises(ValueError):
            invalid.validate()


def test_two_audio_recipes_restore_idle_with_independent_source_ids(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "session.datelier.json"
    editor = EditorSession()
    expected = []
    try:
        for i, name in enumerate(("a", "b")):
            path = tmp_path / (name + ".wav")
            sf.write(path, np.full((100, 2), 0.25 + i * 0.25), 8000, subtype="DOUBLE")
            file = editor.new_tab(path)
            expected.append(
                replace(
                    AudioSettings(),
                    range=AudioRange(10, 50),
                    thresholds=AudioThresholds(0.8, 0.01),
                    channel=i,
                )
            )
        wait(editor)
        files = [
            file for file in editor.file_sessions if file.loader.active is not None
        ]
        assert len(files) == 2
        for file, settings in zip(files, expected, strict=True):
            assert file.loader.active is not None
            dataset = file.loader.active.dataset
            assert dataset.role("path").role == ColumnRole.AUDIO
            file.audio.settings = settings
            file.audio.sync(file)
            file.audio.jobs.request_record(dataset, "path", 0)
        wait(editor)
        for file in files:
            assert file.audio.jobs.active is file.audio.jobs.profile is None
            file.audio.jobs.request_profile(
                AudioRange(), file.audio.settings.thresholds, file.arrays.store
            )
        wait(editor)
        profiles = [file.audio.jobs.profile for file in files]
        assert profiles[0] is not None and profiles[1] is not None
        assert (
            profiles[0].locator.origin.row_id == profiles[1].locator.origin.row_id == 0
        )
        assert profiles[0].locator.origin.file_id != profiles[1].locator.origin.file_id
        save_snapshot(workspace, capture_session(editor), False)
        text = workspace.read_text()
        assert "AudioSignalProfile" not in text and "PreparedAudio" not in text
    finally:
        editor.close()
    restored = EditorSession()
    try:
        restored.open_workspace(workspace)
        wait(restored)
        files = [
            file for file in restored.file_sessions if file.loader.active is not None
        ]
        assert len(files) == 2
        assert [file.audio.settings for file in files] == expected
        for file in files:
            assert (
                file.audio.jobs.active
                is file.audio.jobs.profile
                is file.audio.jobs.metadata
                is None
            )
            assert not file.audio.jobs.busy and file.arrays.store.temporary_path is None
    finally:
        restored.close()
