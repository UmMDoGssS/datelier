"""Explicit audio profile commands compose the shared collection sampling form."""

from collections.abc import Callable
from dataclasses import replace

from datelier.application.audio import AudioController
from datelier.gui.components.actions import CommandButton, JobFeedback, JobSnapshot
from datelier.gui.components.base import Container
from datelier.gui.context.audio_sampling import AudioSamplingFields
from datelier.inspection.audio.collections.settings import AudioCollectionSettings


class AudioProfileSettings(Container):
    def __init__(self, model: AudioController, column: Callable[[], str]) -> None:
        def read() -> AudioCollectionSettings:
            return replace(
                model.settings.collection,
                array_sample_rate=model.settings.array_sample_rate,
            )

        def write(value: AudioCollectionSettings) -> None:
            model.settings = replace(
                model.settings,
                collection=value,
                array_sample_rate=value.array_sample_rate,
            )

        super().__init__(
            "audio-profile-settings",
            (
                CommandButton(
                    "prepare",
                    "Prepare audio collection",
                    lambda: model.request_collection(column()),
                    lambda: not model.collection.busy,
                ),
                JobFeedback(
                    "collection-job",
                    lambda: JobSnapshot(
                        model.collection.message,
                        model.collection.busy,
                        str(model.collection.progress.value),
                    ),
                    model.collection.abandon,
                ),
                AudioSamplingFields(read, write),
            ),
        )
