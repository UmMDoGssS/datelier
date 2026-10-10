"""Explicit header/signal collection profiles keep scopes separate from playback."""

from collections.abc import Callable
from dataclasses import replace

from datelier.application.audio import AudioController
from datelier.gui.components.actions import CommandButton, JobFeedback, JobSnapshot
from datelier.gui.components.base import Container
from datelier.gui.components.fields import ChoiceField, FloatField, IntegerField
from datelier.gui.components.groups import Conditional
from datelier.inspection.audio.collections.settings import (
    AudioProfileMode,
    AudioScopeMode,
)


class AudioProfileSettings(Container):
    def __init__(self, model: AudioController, column: Callable[[], str]) -> None:
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
                ChoiceField(
                    "mode",
                    "Statistics",
                    tuple(AudioProfileMode),
                    lambda: model.settings.collection.mode,
                    lambda value: setattr(
                        model,
                        "settings",
                        replace(
                            model.settings,
                            collection=replace(model.settings.collection, mode=value),
                        ),
                    ),
                ),
                ChoiceField(
                    "scope",
                    "Records",
                    tuple(AudioScopeMode),
                    lambda: model.settings.collection.scope.mode,
                    lambda value: setattr(
                        model,
                        "settings",
                        replace(
                            model.settings,
                            collection=replace(
                                model.settings.collection,
                                scope=replace(
                                    model.settings.collection.scope, mode=value
                                ),
                            ),
                        ),
                    ),
                ),
                IntegerField(
                    "start",
                    "Start row (1-based)",
                    lambda: model.settings.collection.scope.start,
                    lambda value: setattr(
                        model,
                        "settings",
                        replace(
                            model.settings,
                            collection=replace(
                                model.settings.collection,
                                scope=replace(
                                    model.settings.collection.scope, start=value
                                ),
                            ),
                        ),
                    ),
                    1,
                ),
                IntegerField(
                    "count",
                    "Rows",
                    lambda: model.settings.collection.scope.count,
                    lambda value: setattr(
                        model,
                        "settings",
                        replace(
                            model.settings,
                            collection=replace(
                                model.settings.collection,
                                scope=replace(
                                    model.settings.collection.scope, count=value
                                ),
                            ),
                        ),
                    ),
                    1,
                ),
                IntegerField(
                    "seed",
                    "Seed",
                    lambda: model.settings.collection.scope.seed,
                    lambda value: setattr(
                        model,
                        "settings",
                        replace(
                            model.settings,
                            collection=replace(
                                model.settings.collection,
                                scope=replace(
                                    model.settings.collection.scope, seed=value
                                ),
                            ),
                        ),
                    ),
                    0,
                    2**32 - 1,
                ),
                IntegerField(
                    "rate",
                    "Array rate (0 = unknown)",
                    lambda: model.settings.array_sample_rate or 0,
                    lambda value: setattr(
                        model,
                        "settings",
                        replace(model.settings, array_sample_rate=value or None),
                    ),
                    0,
                    768000,
                ),
                Conditional(
                    "thresholds",
                    lambda: model.settings.collection.mode == AudioProfileMode.SIGNAL,
                    (
                        FloatField(
                            "silence",
                            "Silence amplitude",
                            lambda: model.settings.collection.thresholds.silence,
                            lambda value: setattr(
                                model,
                                "settings",
                                replace(
                                    model.settings,
                                    collection=replace(
                                        model.settings.collection,
                                        thresholds=replace(
                                            model.settings.collection.thresholds,
                                            silence=value,
                                        ),
                                    ),
                                ),
                            ),
                            0,
                            1e300,
                        ),
                        FloatField(
                            "clipping",
                            "Clipping amplitude (0 = original rails)",
                            lambda: model.settings.collection.thresholds.clipping or 0,
                            lambda value: setattr(
                                model,
                                "settings",
                                replace(
                                    model.settings,
                                    collection=replace(
                                        model.settings.collection,
                                        thresholds=replace(
                                            model.settings.collection.thresholds,
                                            clipping=value or None,
                                        ),
                                    ),
                                ),
                            ),
                            0,
                            1e300,
                        ),
                    ),
                ),
            ),
        )
