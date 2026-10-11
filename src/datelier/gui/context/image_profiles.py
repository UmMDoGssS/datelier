"""Explicit image scopes and prepared-result display settings."""

from collections.abc import Callable
from dataclasses import replace

from datelier.application.media.images import ImageController
from datelier.gui.components.actions import CommandButton, JobFeedback, JobSnapshot
from datelier.gui.components.base import Container
from datelier.gui.components.bindings import StateFields
from datelier.gui.components.groups import Conditional
from datelier.gui.context.image_sampling import ImageSamplingFields


class ImageProfileSettings(Container):
    def __init__(self, model: ImageController, column: Callable[[], str]) -> None:
        fields = StateFields(
            lambda: model.settings.profile,
            lambda value: setattr(
                model, "settings", replace(model.settings, profile=value)
            ),
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
                ImageSamplingFields(fields.read, fields.write),
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
