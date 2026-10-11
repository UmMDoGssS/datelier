"""Saved mappings, explicit scans, source links and partial recovery without sound."""

from dataclasses import replace
from pathlib import Path
from time import monotonic, sleep
from unittest.mock import patch

import numpy as np
import pytest
import soundfile as sf

from datelier.application.comparisons.base import ComparisonFamily
from datelier.application.editor import EditorController
from datelier.inspection.arrays.mapping import (
    ArrayLayout,
    ArrayRecordMapping,
    SupportingArray,
)
from datelier.inspection.audio.collections.settings import (
    AudioCollectionSettings,
    AudioProfileMode,
    AudioScope,
)
from datelier.inspection.audio.comparisons.settings import (
    AudioComparisonSettings,
    AudioComparisonSource,
    AudioComparisonViewSettings,
)
from datelier.inspection.audio.playback.controller import PlaybackPhase
from datelier.inspection.references.types import ReferenceSettings
from datelier.io.loading import LoadPhase
from datelier.pipeline.operations import Sort
from datelier.workspace.codec import decode_record, encode
from datelier.workspace.session_storage import read_session_workspace
from datelier.workspace.session_types import SessionFile, SessionWorkspace


def wait(editor: EditorController, root: Path) -> None:
    deadline = monotonic() + 5
    while monotonic() < deadline:
        editor.poll()
        for file in editor.all_files:
            if file.loader.active is not None and file.references.settings.roots != (
                str(root),
            ):
                file.references.configure(ReferenceSettings(roots=(str(root),)))
        if (
            not editor.opening.busy
            and not editor.workspace.busy
            and not editor.compare.audio.jobs.busy
            and all(
                file.loader.status.phase != LoadPhase.LOADING
                and not file.editor.busy
                and not file.references.busy
                for file in editor.all_files
            )
        ):
            return
        sleep(0.001)
    raise AssertionError("Audio comparison editor did not settle")


def test_legacy_session_defaults_and_invalid_audio_recipes() -> None:
    workspace = SessionWorkspace((SessionFile("empty"),), "empty")
    raw = encode(workspace)
    assert isinstance(raw, dict)
    for key in ("audio_comparisons", "audio_comparison_index", "audio_comparison_view"):
        raw.pop(key)
    assert decode_record(SessionWorkspace, raw) == workspace
    invalid = replace(
        workspace,
        audio_comparisons=(
            AudioComparisonSettings(
                (AudioComparisonSource("closed", AudioCollectionSettings("audio")),)
            ),
        ),
    )
    with pytest.raises(ValueError, match="closed file"):
        invalid.validate()
    with pytest.raises(ValueError, match="scope"):
        AudioScope(count=0).validate()
    with pytest.raises(ValueError, match="unit family"):
        AudioComparisonViewSettings(channel=-1).validate()


def test_saved_audio_comparison_links_correct_file_and_recovery_stays_idle(
    tmp_path: Path,
) -> None:
    for name, frames in (("short", 4), ("long", 8)):
        sf.write(
            tmp_path / f"{name}.wav", np.full((frames, 2), 0.25), 4, subtype="DOUBLE"
        )
    paths = (tmp_path / "train.csv", tmp_path / "test.csv")
    paths[0].write_text("audio,label\nshort.wav,a\nlong.wav,z\n")
    paths[1].write_text("audio,label\nlong.wav,z\nshort.wav,a\n")
    workspace = tmp_path / "session.datelier.json"
    editor = EditorController()
    try:
        editor.opening.request(paths, editor.active_id)
        wait(editor, tmp_path)
        first, second = editor.files
        second.editor.request(Sort(("label",)))
        wait(editor, tmp_path)
        recipe = AudioComparisonSettings(
            tuple(
                AudioComparisonSource(
                    file.identity,
                    AudioCollectionSettings("audio", mode=AudioProfileMode.SIGNAL),
                )
                for file in editor.files
            ),
            2,
        )
        view = AudioComparisonViewSettings(
            metric="RMS",
            family="full-scale amplitude",
            channel=1,
            source=1,
            height=200,
            proportions=False,
        )
        editor.compare.audio.restore((recipe,))
        editor.compare.audio.view = view
        editor.compare.tab = ComparisonFamily.AUDIO
        editor.poll()
        assert (
            editor.compare.audio.jobs.started == 0
            and editor.compare.audio.jobs.active is None
        )
        editor.compare.audio.jobs.request()
        wait(editor, tmp_path)
        result = editor.compare.audio.jobs.active
        assert result is not None
        duration = next(c for c in result.curves if c.metric.name == "Duration")
        editor.compare.audio.select(1, duration.metric, 1)
        deadline = monotonic() + 5
        while not second.selection.row_ids and monotonic() < deadline:
            editor.poll()
            sleep(0.001)
        assert second.selection.row_ids == {0} and not first.selection.row_ids
        assert editor.active is second and second.table.target_row == 2
        editor.compare.audio.open_record(result, 0, 0)
        assert editor.active is first and first.selection.row_ids == {0}
        assert first.views.tab == "Inspect"
        assert (
            editor.playback.snapshot.phase == PlaybackPhase.IDLE
            and editor.playback.snapshot.request is None
        )
        editor.save_workspace(workspace, "", (), False, False)
        wait(editor, tmp_path)
        saved = read_session_workspace(workspace)
        assert (
            saved.audio_comparisons == (recipe,) and saved.audio_comparison_view == view
        )
        assert saved.comparison_tab == "Audio"
        assert (
            "channel_records" not in workspace.read_text()
            and "PlaybackRun" not in workspace.read_text()
        )
        paths[0].rename(tmp_path / "moved.csv")
        with patch(
            "datelier.inspection.audio.comparisons.jobs.prepare_comparison",
            side_effect=AssertionError("Restore scanned audio"),
        ):
            editor.open_workspace(workspace)
            wait(editor, tmp_path)
        failed, good = editor.files
        assert failed.recovery and good.loader.active
        assert (
            editor.compare.audio.recipes == (recipe,)
            and editor.compare.audio.view == view
        )
        assert (
            editor.compare.audio.jobs.active is None
            and not editor.compare.audio.jobs.busy
        )
        assert (
            editor.compare.audio.jobs.started == 1
            and editor.playback.snapshot.request is None
        )
        with pytest.raises(ValueError, match="changed"):
            editor.compare.audio.open_record(result, 0, 0)
        editor.recover(failed.identity, tmp_path / "moved.csv", False)
        wait(editor, tmp_path)
        assert failed.loader.active and editor.compare.audio.jobs.active is None
        editor.close_file(failed.identity)
        assert editor.compare.audio.recipes[0].sources == (recipe.sources[1],)
        editor.save_workspace(tmp_path / "closed.datelier.json", "", (), False, False)
        wait(editor, tmp_path)
        assert editor.workspace.saved is not None
    finally:
        editor.close()


def test_mapped_record_view_comparison_preserves_support_and_closes_independently(
    tmp_path: Path,
) -> None:
    source = tmp_path / "waves.npz"
    np.savez_compressed(
        source,
        waves=np.array([[0.25] * 4, [0.5] * 4], dtype=np.float32),
        labels=np.array([2, 1]),
    )
    sf.write(tmp_path / "tone.wav", np.zeros(4), 4, subtype="DOUBLE")
    editor = EditorController()
    try:
        owner = editor.new_file(source)
        file = editor.new_file(tmp_path / "tone.wav")
        wait(editor, tmp_path)
        mapping = ArrayRecordMapping(
            "waves",
            layout=ArrayLayout.AUDIO,
            display_axes=(1,),
            supporting=(SupportingArray("labels", "label"),),
        )
        view = owner.record_views.open_array(owner, mapping)
        deadline = monotonic() + 5
        while view.loader.active is None and monotonic() < deadline:
            editor.poll()
            sleep(0.001)
        assert view.loader.active is not None
        view.editor.request(Sort(("label",)))
        wait(editor, tmp_path)
        recipe = AudioComparisonSettings(
            (
                AudioComparisonSource(file.identity, AudioCollectionSettings("path")),
                AudioComparisonSource(
                    view.identity,
                    AudioCollectionSettings(
                        "waves", mode=AudioProfileMode.SIGNAL, array_sample_rate=4
                    ),
                ),
            ),
            2,
        )
        editor.compare.audio.restore((recipe,))
        editor.poll()
        editor.compare.audio.jobs.request()
        wait(editor, tmp_path)
        result = editor.compare.audio.jobs.active
        assert result is not None and result.profiles[1].records[
            "row_id"
        ].to_list() == [1, 0]
        editor.compare.audio.open_record(result, 1, 0)
        assert editor.active is owner and owner.record_views.active_id == view.identity
        assert view.selection.row_ids == {1} and not file.selection.row_ids
        assert view.audio.settings.array_sample_rate == 4
        assert view.loader.active.dataset.table["label"].to_list() == [1, 2]
        assert editor.playback.snapshot.request is None
        owner.record_views.close_view(view.identity)
        editor.poll()
        assert editor.compare.audio.recipes[0].sources == (recipe.sources[0],)
        assert editor.compare.audio.jobs.active is None
    finally:
        editor.close()
