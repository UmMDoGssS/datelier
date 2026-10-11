"""Independent audio scopes/thresholds/drafts and restored view state stay explicit."""

from dataclasses import replace
from pathlib import Path

import numpy as np
import soundfile as sf
from test_rebuild_comparisons import until

from datelier.application.editor import EditorController
from datelier.application.workspace import capture_session
from datelier.inspection.audio.collections.settings import (
    AudioProfileMode,
    AudioScope,
    AudioScopeMode,
)
from datelier.inspection.audio.comparisons.settings import AudioComparisonViewSettings
from datelier.inspection.audio.playback.controller import PlaybackPhase
from datelier.inspection.audio.profile_types import AudioThresholds
from datelier.workspace.session_jobs import save_snapshot


def test_linked_scope_thresholds_drafts_and_idle_restore(tmp_path: Path) -> None:
    wav, first, second = tmp_path / "signal.wav", tmp_path / "a.csv", tmp_path / "b.csv"
    sf.write(wav, np.array([0.1, 0.2, 0.3, 0.4]), 4, subtype="DOUBLE")
    first.write_text("label,audio\na,signal.wav\nb,signal.wav\n")
    second.write_text("label,path\nx,signal.wav\ny,signal.wav\n")
    originals = wav.read_bytes(), first.read_bytes(), second.read_bytes()
    workspace = tmp_path / "session.json"
    editor = EditorController()
    try:
        a = editor.active
        a.open(first)
        b = editor.new_file(second)
        until(
            editor,
            lambda: (
                a.inspection is not None
                and b.inspection is not None
                and not a.references.busy
                and not b.references.busy
            ),
        )
        assert a.inspection
        a.selection.choose(a.inspection.dataset.revision, (1,))
        editor.poll()
        model = editor.compare.audio
        model.map_files((a.identity, b.identity))
        assert tuple(s.profile.column for s in model.draft.sources) == ("audio", "path")
        for mapping in model.draft.sources:
            profile = replace(
                mapping.profile,
                mode=AudioProfileMode.SIGNAL,
                thresholds=AudioThresholds(
                    silence=0.15 if mapping.file_id == a.identity else 0.35
                ),
                scope=AudioScope(AudioScopeMode.SELECTION)
                if mapping.file_id == a.identity
                else AudioScope(),
            )
            model.update_mapping(replace(mapping, profile=profile))
        model.draft = replace(model.draft, bins=2)
        editor.poll()
        assert model.active is None and model.jobs.started == 0
        model.prepare()
        until(editor, lambda: model.active is not None)
        result = model.active
        assert result
        assert [p.ready for p in result.profiles] == [1, 2]
        assert len(model.statistics) == 2
        assert result.profiles[0].records["row_id"].to_list() == [1]
        assert model.plot and len(model.plot.series) == 2
        model.draft = replace(model.draft, bins=12)
        editor.poll()
        assert model.active is result and model.changed
        model.open_record(result, 0, 0)
        assert editor.current is a and a.records.settings.primary == "audio"
        assert a.audio.settings.thresholds.silence == 0.15
        editor.activate(b.identity)
        b.selection.choose(
            b.inspection.dataset.revision, (0,)
        ) if b.inspection else None
        editor.poll()
        assert model.active is result
        model.view = AudioComparisonViewSettings(
            "Statistics", "RMS", "full-scale amplitude", 0, False, 1, 1, 0
        )
        save_snapshot(workspace, capture_session(editor), False)
        a.selection.choose(a.inspection.dataset.revision, (0,))
        editor.poll()
        assert model.active is None and model.jobs.started == 1
        assert (
            editor.playback.snapshot.phase == PlaybackPhase.IDLE
            and editor.playback.snapshot.request is None
        )
        assert originals == (wav.read_bytes(), first.read_bytes(), second.read_bytes())
    finally:
        editor.close()
    reopened = EditorController()
    try:
        reopened.open_workspace(workspace)
        until(reopened, lambda: not reopened.workspace.busy)
        model = reopened.compare.audio
        assert model.active is None and model.jobs.started == 0
        assert model.view == AudioComparisonViewSettings(
            "Statistics", "RMS", "full-scale amplitude", 0, False, 1, 1, 0
        )
        assert model.recipes[0].sources[0].profile.thresholds.silence == 0.15
        assert not reopened.playback.snapshot.request
    finally:
        reopened.close()
