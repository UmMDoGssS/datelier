"""Common scope, decode level, rate and threshold fields for audio collections."""

from collections.abc import Callable
from dataclasses import replace

from datelier.gui.components.inputs import FloatField, StateFields
from datelier.gui.components.layout import Group
from datelier.gui.components.layout.groups import Conditional
from datelier.inspection.audio.collections.settings import (
    AudioCollectionSettings,
    AudioProfileMode,
    AudioScopeMode,
)


class AudioSamplingFields(Group):
    def __init__(
        self,
        read: Callable[[], AudioCollectionSettings],
        write: Callable[[AudioCollectionSettings], None],
    ) -> None:
        fields = StateFields(read, write)
        scope = StateFields(
            lambda: read().scope, lambda s: write(replace(read(), scope=s))
        )
        thresholds = StateFields(
            lambda: read().thresholds, lambda s: write(replace(read(), thresholds=s))
        )
        super().__init__(
            "audio-sampling",
            (
                fields.choice(
                    "mode",
                    "Statistics",
                    tuple(AudioProfileMode),
                    lambda s: s.mode,
                    lambda s, v: replace(s, mode=v),
                ),
                scope.choice(
                    "scope",
                    "Records",
                    tuple(AudioScopeMode),
                    lambda s: s.mode,
                    lambda s, v: replace(s, mode=v),
                ),
                Conditional(
                    "range",
                    lambda: scope.read().mode == AudioScopeMode.RANGE,
                    (
                        scope.integer(
                            "start",
                            "Start row (1-based)",
                            lambda s: s.start,
                            lambda s, v: replace(s, start=v),
                            1,
                        ),
                    ),
                ),
                Conditional(
                    "bounded",
                    lambda: (
                        scope.read().mode
                        in (AudioScopeMode.RANGE, AudioScopeMode.RANDOM)
                    ),
                    (
                        scope.integer(
                            "count",
                            "Rows",
                            lambda s: s.count,
                            lambda s, v: replace(s, count=v),
                            1,
                        ),
                    ),
                ),
                Conditional(
                    "random",
                    lambda: scope.read().mode == AudioScopeMode.RANDOM,
                    (
                        scope.integer(
                            "seed",
                            "Record seed",
                            lambda s: s.seed,
                            lambda s, v: replace(s, seed=v),
                            0,
                            2**32 - 1,
                        ),
                    ),
                ),
                fields.integer(
                    "rate",
                    "Array rate (0 = unknown)",
                    lambda s: s.array_sample_rate or 0,
                    lambda s, v: replace(s, array_sample_rate=v or None),
                    0,
                    768000,
                ),
                Conditional(
                    "thresholds",
                    lambda: read().mode == AudioProfileMode.SIGNAL,
                    (
                        FloatField(
                            "silence",
                            "Silence amplitude",
                            lambda: thresholds.read().silence,
                            lambda v: thresholds.write(
                                replace(thresholds.read(), silence=v)
                            ),
                            0,
                            1e300,
                        ),
                        FloatField(
                            "clipping",
                            "Clipping amplitude (0 = original rails)",
                            lambda: thresholds.read().clipping or 0,
                            lambda v: thresholds.write(
                                replace(thresholds.read(), clipping=v or None)
                            ),
                            0,
                            1e300,
                        ),
                    ),
                ),
            ),
        )
