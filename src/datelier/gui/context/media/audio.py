"""Contextual audio controls over narrow media state."""

from dataclasses import replace

from datelier.application.media.audio import AudioController
from datelier.application.media.records import RecordKind
from datelier.gui.components.inputs import FloatField, IntegerField
from datelier.gui.components.layout.groups import Collapsible, Conditional
from datelier.gui.context.audio import SignalSettings
from datelier.gui.context.media.base import MediaSettings


class AudioSettings(MediaSettings):
    @property
    def kind(self) -> RecordKind:
        return RecordKind.AUDIO

    def __init__(self, model: AudioController) -> None:
        super().__init__(
            "audio-settings",
            (
                IntegerField(
                    "start",
                    "First sample frame",
                    lambda: model.settings.range.start,
                    lambda value: setattr(
                        model,
                        "settings",
                        replace(
                            model.settings,
                            range=replace(model.settings.range, start=value),
                        ),
                    ),
                    0,
                ),
                IntegerField(
                    "stop",
                    "End sample frame (exclusive; 0 = end)",
                    lambda: model.settings.range.stop or 0,
                    lambda value: setattr(
                        model,
                        "settings",
                        replace(
                            model.settings,
                            range=replace(model.settings.range, stop=value or None),
                        ),
                    ),
                    0,
                ),
                IntegerField(
                    "channel",
                    "Channel (0-based)",
                    lambda: model.settings.channel,
                    lambda value: setattr(
                        model, "settings", replace(model.settings, channel=value)
                    ),
                    0,
                ),
                IntegerField(
                    "array-rate",
                    "Array sample rate (0 = unknown)",
                    lambda: model.settings.array_sample_rate or 0,
                    lambda value: setattr(
                        model,
                        "settings",
                        replace(model.settings, array_sample_rate=value or None),
                    ),
                    0,
                    768000,
                ),
            ),
        )

        self.children += (
            Conditional(
                "time",
                lambda: model.sample_rate is not None,
                (
                    Collapsible(
                        "time-range",
                        "Select by original time",
                        (
                            FloatField(
                                "start-time",
                                "Start time (s)",
                                lambda: model.start_seconds,
                                model.set_start_seconds,
                            ),
                            FloatField(
                                "stop-time",
                                "End time (s)",
                                lambda: model.stop_seconds,
                                model.set_stop_seconds,
                            ),
                        ),
                    ),
                ),
            ),
            SignalSettings(model),
        )
