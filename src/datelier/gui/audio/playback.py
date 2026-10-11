"""Only explicit listening commands start a stream or enumerate devices."""

from dataclasses import replace

from imgui_bundle import imgui

from datelier.application.media.audio import AudioController
from datelier.gui.components.actions import CommandButton
from datelier.gui.components.base import Container, FrameContext
from datelier.gui.components.fields import (
    BooleanField,
    ChoiceField,
    FloatField,
    IntegerField,
)
from datelier.inspection.audio.playback.controller import PlaybackPhase


class PlaybackControls(Container):
    def __init__(self, model: AudioController) -> None:
        self.model = model
        self.seek_frame = 0
        super().__init__(
            "playback",
            (
                CommandButton(
                    "play",
                    "Play original audio",
                    model.play,
                    lambda: (
                        model.jobs.metadata is not None
                        and model.jobs.metadata[1].sample_rate is not None
                    ),
                ),
                CommandButton(
                    "pause",
                    "Pause / Resume",
                    model.pause,
                    lambda: (
                        model.player.snapshot.phase
                        in (PlaybackPhase.PLAYING, PlaybackPhase.PAUSED)
                    ),
                ),
                CommandButton("stop", "Stop", model.stop),
                FloatField(
                    "volume",
                    "Listening volume",
                    lambda: model.settings.playback.volume,
                    model.set_volume,
                    0,
                    1,
                ),
                BooleanField(
                    "range",
                    "Play selected range",
                    lambda: model.settings.playback.selected_range,
                    lambda value: setattr(
                        model,
                        "settings",
                        replace(
                            model.settings,
                            playback=replace(
                                model.settings.playback, selected_range=value
                            ),
                        ),
                    ),
                ),
                BooleanField(
                    "channel",
                    "Play selected channel",
                    lambda: model.settings.playback.selected_channel,
                    lambda value: setattr(
                        model,
                        "settings",
                        replace(
                            model.settings,
                            playback=replace(
                                model.settings.playback, selected_channel=value
                            ),
                        ),
                    ),
                ),
                IntegerField(
                    "seek",
                    "Seek to original frame",
                    lambda: model.settings.playback.seek_frame or 0,
                    lambda value: setattr(
                        model,
                        "settings",
                        replace(
                            model.settings,
                            playback=replace(model.settings.playback, seek_frame=value),
                        ),
                    ),
                ),
                CommandButton(
                    "apply-seek",
                    "Seek",
                    lambda: model.seek(model.settings.playback.seek_frame or 0),
                    lambda: (
                        model.player.snapshot.phase
                        in (PlaybackPhase.PLAYING, PlaybackPhase.PAUSED)
                    ),
                ),
                CommandButton(
                    "outputs", "Check output devices", model.player.devices.request
                ),
                ChoiceField(
                    "device",
                    "Output device",
                    lambda: (
                        None,
                        *(choice.query for choice in model.player.devices.choices),
                    ),
                    lambda: model.settings.playback.device,
                    lambda value: setattr(
                        model,
                        "settings",
                        replace(
                            model.settings,
                            playback=replace(model.settings.playback, device=value),
                        ),
                    ),
                ),
            ),
        )

    def render(self, frame: FrameContext) -> None:
        state = self.model.player.snapshot
        imgui.text_wrapped(f"{state.phase}: {state.message}")
        if state.request:
            imgui.text_wrapped(
                f"Original frame {state.position:,} / {state.request.range.stop:,} · "
                f"{state.request.metadata.sample_rate} Hz · "
                f"{state.underruns:,} underruns · {state.nonfinite:,} nonfinite samples"
            )
            if state.conversion:
                imgui.text_wrapped(state.conversion)
        super().render(frame)
        imgui.text_wrapped(self.model.player.devices.message)
