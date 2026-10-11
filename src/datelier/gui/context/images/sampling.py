"""One reusable typed scope/pixel form for image profiles and comparisons."""

from collections.abc import Callable
from dataclasses import replace

from datelier.gui.components.inputs import StateFields
from datelier.gui.components.layout import Group
from datelier.gui.components.layout.groups import Conditional
from datelier.inspection.images.profiles import (
    ImageProfileSettings,
    ImageScopeMode,
    PixelScope,
)


class ImageSamplingFields(Group):
    def __init__(
        self,
        read: Callable[[], ImageProfileSettings],
        write: Callable[[ImageProfileSettings], None],
    ) -> None:
        fields = StateFields(read, write)
        scope = StateFields(
            lambda: read().scope, lambda s: write(replace(read(), scope=s))
        )
        super().__init__(
            "image-sampling",
            (
                scope.choice(
                    "scope",
                    "Records",
                    tuple(ImageScopeMode),
                    lambda s: s.mode,
                    lambda s, v: replace(s, mode=v),
                ),
                Conditional(
                    "range",
                    lambda: scope.read().mode == ImageScopeMode.RANGE,
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
                        in (ImageScopeMode.RANGE, ImageScopeMode.RANDOM)
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
                    lambda: scope.read().mode == ImageScopeMode.RANDOM,
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
                fields.choice(
                    "pixels",
                    "Pixels",
                    tuple(PixelScope),
                    lambda s: s.pixels,
                    lambda s, v: replace(s, pixels=v),
                ),
                Conditional(
                    "sample",
                    lambda: read().pixels == PixelScope.SAMPLE,
                    (
                        fields.integer(
                            "count",
                            "Pixels per image",
                            lambda s: s.pixel_count,
                            lambda s, v: replace(s, pixel_count=v),
                            1,
                        ),
                        fields.integer(
                            "seed",
                            "Pixel seed",
                            lambda s: s.pixel_seed,
                            lambda s, v: replace(s, pixel_seed=v),
                            0,
                            2**32 - 1,
                        ),
                    ),
                ),
            ),
        )
