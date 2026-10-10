"""Explicit image scopes and prepared-result display settings."""

from collections.abc import Callable
from dataclasses import replace

from datelier.application.images import ImageController
from datelier.gui.components.actions import CommandButton, JobFeedback, JobSnapshot
from datelier.gui.components.base import Container
from datelier.gui.components.bindings import StateFields
from datelier.gui.components.groups import Conditional
from datelier.inspection.images.profile_types import ImageScopeMode, PixelScope


class ImageProfileSettings(Container):
    def __init__(self, model: ImageController, column: Callable[[], str]) -> None:
        fields = StateFields(
            lambda: model.settings.profile,
            lambda value: setattr(
                model, "settings", replace(model.settings, profile=value)
            ),
        )
        scope = StateFields(
            lambda: model.settings.profile.scope,
            lambda value: fields.write(replace(fields.read(), scope=value)),
        )
        view = StateFields(
            lambda: model.settings.profile_view,
            lambda value: setattr(
                model, "settings", replace(model.settings, profile_view=value)
            ),
        )
        super().__init__(
            "image-profile-settings",
            (
                CommandButton(
                    "prepare",
                    "Prepare image collection",
                    lambda: model.request_collection(column()),
                    lambda: not model.profile_jobs.busy,
                ),
                JobFeedback(
                    "collection-job",
                    lambda: JobSnapshot(
                        model.profile_jobs.message,
                        model.profile_jobs.busy,
                        str(model.profile_jobs.progress.value),
                    ),
                    model.abandon_profile,
                ),
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
                    lambda: fields.read().pixels == PixelScope.SAMPLE,
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
                fields.integer(
                    "bins",
                    "Histogram bins",
                    lambda s: s.bins,
                    lambda s, v: replace(s, bins=v),
                    1,
                    256,
                ),
                Conditional(
                    "dimensions",
                    lambda: view.read().tab == "Dimensions",
                    (
                        view.choice(
                            "dimension",
                            "Dimension",
                            ("Width", "Height", "Aspect ratio"),
                            lambda s: s.dimension,
                            lambda s, v: replace(s, dimension=v),
                        ),
                    ),
                ),
                Conditional(
                    "colors",
                    lambda: view.read().tab == "Colors",
                    (
                        view.choice(
                            "group",
                            "Channel family (mode, dtype)",
                            lambda: model.channel_groups,
                            lambda s: (s.group_mode, s.group_dtype),
                            lambda s, v: replace(s, group_mode=v[0], group_dtype=v[1]),
                        ),
                    ),
                ),
            ),
        )
