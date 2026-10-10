"""Contextual images controls over narrow media state."""

from dataclasses import replace

from datelier.application.images import ImageController
from datelier.application.records import RecordKind
from datelier.gui.components.base import FrameContext
from datelier.gui.components.fields import ChoiceField
from datelier.gui.context.media.base import MediaSettings
from datelier.inspection.heatmaps import Colormap


class ImageSettings(MediaSettings):
    @property
    def kind(self) -> RecordKind:
        return RecordKind.IMAGE

    def __init__(self, model: ImageController) -> None:
        super().__init__("image-settings", ())
        self.model = model
        self.channel: ChoiceField[int | None] | None = None
        self._count = -1
        self.colormap = ChoiceField(
            "colormap",
            "Heatmap colors",
            tuple(Colormap),
            lambda: model.settings.display.colormap,
            lambda value: setattr(
                model,
                "settings",
                replace(
                    model.settings,
                    display=replace(model.settings.display, colormap=value),
                ),
            ),
        )

    def render(self, frame: FrameContext) -> None:
        prepared = self.model.jobs.metadata
        count = prepared[1].count if prepared else 0
        if self._count != count:
            self._count = count
            self.channel = ChoiceField(
                "channel",
                "Channel",
                (None, *range(count)),
                lambda: self.model.settings.display.channel,
                lambda value: setattr(
                    self.model,
                    "settings",
                    replace(
                        self.model.settings,
                        display=replace(self.model.settings.display, channel=value),
                    ),
                ),
                ("All channels", *(str(i) for i in range(count))),
            )
        self.children = (
            (self.channel, self.colormap) if self.channel else (self.colormap,)
        )
        super().render(frame)
