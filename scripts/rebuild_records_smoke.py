"""Native original-image/text/audio record-family gates for the rebuild."""

import json
from dataclasses import replace
from pathlib import Path
from tempfile import TemporaryDirectory

import numpy as np
import polars as pl
import soundfile as sf
from imgui_bundle import hello_imgui, imgui
from PIL import Image

from datelier.application.editor import EditorController
from datelier.gui.app import InspectionEvidence, run_gui
from datelier.gui.components.probe import GuiProbe
from datelier.inspection.audio.signal import WaveformEnvelope
from datelier.inspection.text.types import Normalization, TokenMode


def main() -> None:
    with TemporaryDirectory(prefix="datelier-rebuild-records-") as directory:
        root = Path(directory)
        rgba = np.zeros((60, 80, 3), dtype=np.uint8)
        rgba[:, :, 0] = np.arange(80, dtype=np.uint8)
        Image.fromarray(rgba).save(root / "image.png")
        signal = np.sin(2 * np.pi * 440 * np.arange(16000) / 16000)
        sf.write(root / "audio.wav", signal, 16000)
        source = root / "data.csv"
        pl.DataFrame(
            {
                "image": ["image.png"],
                "audio": ["audio.wav"],
                "text": ["A e\u0301 multilingual 文本 " * 100],
            }
        ).write_csv(source)
        original = {
            p: p.read_bytes() for p in (source, root / "image.png", root / "audio.wav")
        }
        stage, entered = 0, 0
        clicking: tuple[float, float] | None = None
        click_stage = 0
        next_stage = 0
        done = False

        def target(probe: GuiProbe, suffix: tuple[str, ...]) -> tuple[float, float]:
            return next(
                value
                for key, value in probe.targets.items()
                if key.path[-len(suffix) :] == suffix
            )

        def frame(
            editor: EditorController, probe: GuiProbe, evidence: InspectionEvidence
        ) -> None:
            nonlocal stage, entered, clicking, click_stage, next_stage, done
            file, io = editor.current, imgui.get_io()
            age = evidence.frames - entered
            if evidence.frames > 800:
                raise AssertionError(
                    (
                        stage,
                        file.images.jobs.message,
                        file.text.jobs.message,
                        file.audio.jobs.message,
                    )
                )
            if clicking is not None:
                if age < 4:
                    return
                if click_stage == 0:
                    io.add_mouse_button_event(0, True)
                    click_stage, entered = 1, evidence.frames
                elif click_stage == 1:
                    io.add_mouse_button_event(0, False)
                    click_stage, entered = 2, evidence.frames
                else:
                    clicking = None
                    stage, entered = next_stage, evidence.frames
                return
            suffix: tuple[str, ...] | None = None
            if stage == 0 and file.inspection:
                editor.choose_route("Inspect")
                file.records.settings = replace(
                    file.records.settings, primary="image", gallery=False
                )
                stage, entered = 1, evidence.frames
            elif stage == 1 and file.images.jobs.active:
                pixels = file.images.jobs.active
                assert pixels.metadata.width == 80 and pixels.metadata.height == 60
                assert pixels.pixel(5, 4) == (5, 0, 0)
                assert not file.audio.player.snapshot.request
                file.records.settings = replace(file.records.settings, primary="text")
                file.text.jobs.settings = replace(
                    file.text.jobs.settings,
                    tokens=replace(
                        file.text.jobs.settings.tokens,
                        mode=TokenMode.WORD,
                        normalization=Normalization.NFC,
                    ),
                )
                stage, entered = 2, evidence.frames
            elif (
                stage == 2
                and age > 10
                and editor.preferences.ready
                and not file.references.busy
            ):
                suffix, next_stage = ("text", "prepare"), 3
            elif stage == 3 and file.text.jobs.active:
                document = file.text.jobs.active
                assert document.tokens[1].start == 2 and document.tokens[1].end == 4
                file.records.settings = replace(file.records.settings, primary="audio")
                stage, entered = 4, evidence.frames
            elif stage == 4 and file.audio.jobs.metadata and age > 10:
                assert file.audio.jobs.metadata[1].sample_rate == 16000
                assert (
                    file.audio.jobs.active is None and file.audio.signal.active is None
                )
                suffix, next_stage = ("commands", "waveform", "run"), 5
            elif stage == 5 and isinstance(file.audio.signal.active, WaveformEnvelope):
                assert file.audio.signal.active.metadata.frames == 16000
                assert file.audio.player.snapshot.request is None
                assert (
                    file.images.profile_jobs.active is None
                    and file.text.jobs.profile is None
                )
                assert all(p.read_bytes() == raw for p, raw in original.items())
                done = True
                hello_imgui.get_runner_params().app_shall_exit = True
            if suffix:
                try:
                    clicking = target(probe, suffix)
                except StopIteration:
                    return
                io.mouse_pos = imgui.ImVec2(*clicking)
                io.want_set_mouse_pos = True
                click_stage, entered = 0, evidence.frames

        evidence = run_gui(source, on_probe_frame=frame)
        assert done
        report = {
            "frames": evidence.frames,
            "p95_ms": float(np.percentile(evidence.frame_intervals_ms, 95)),
            "image_original_pixels": True,
            "text_original_spans": True,
            "audio_original_waveform": True,
            "source_preserved": True,
            "implicit_collection_playback": 0,
        }
        Path("/tmp/datelier-rebuild-records.json").write_text(
            json.dumps(report, indent=2) + "\n"
        )
        print(json.dumps(report))


if __name__ == "__main__":
    main()
