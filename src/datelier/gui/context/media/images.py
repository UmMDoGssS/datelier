"""Image display, fixed heatmap coordinates and bounded cache controls."""

from dataclasses import replace

from datelier.application.media.images import ImageController
from datelier.application.media.records import RecordKind
from datelier.gui.annotations.settings import AnnotationSettings
from datelier.gui.components.base import Container, FrameContext
from datelier.gui.components.bindings import StateFields
from datelier.gui.components.fields import IntegerField
from datelier.gui.components.groups import Collapsible
from datelier.gui.components.ranges import DisplayRange
from datelier.gui.context.media.base import MediaSettings
from datelier.inspection.heatmaps import Colormap


class ImageCoordinates(Container):
    def __init__(self, model: ImageController) -> None:
        super().__init__("fixed-coordinates", ())
        self.model = model
        self._axes: tuple[tuple[int, int], ...] = ()

    def render(self, frame: FrameContext) -> None:
        axes = self.model.fixed_axes
        if axes != self._axes:
            self._axes = axes
            self.children = tuple(
                IntegerField(
                    f"axis-{axis}",
                    f"Axis {axis} coordinate (0-based)",
                    lambda axis=axis: self.model.fixed_coordinate(axis),
                    lambda value, axis=axis: self.model.set_fixed_coordinate(
                        axis, value
                    ),
                    0,
                    max(0, length - 1),
                )
                for axis, length in axes
            )
        super().render(frame)


class ImageChannel(Container):
    def __init__(self, model: ImageController) -> None:
        fields = StateFields(
            lambda: model.settings.display,
            lambda value: setattr(
                model, "settings", replace(model.settings, display=value)
            ),
        )
        self.model = model
        self.channel = fields.integer(
            "channel",
            "Channel (-1 = all image channels)",
            lambda s: -1 if s.channel is None else s.channel,
            lambda s, v: replace(s, channel=None if v < 0 else v),
            -1,
        )
        super().__init__("channels", (self.channel,))

    def render(self, frame: FrameContext) -> None:
        prepared = self.model.jobs.metadata
        if prepared is None:
            return
        self.channel.maximum = prepared[1].count - 1
        self.channel.minimum = 0 if prepared[1].mode == "Numeric" else -1
        super().render(frame)


class ImageSettings(MediaSettings):
    @property
    def kind(self) -> RecordKind:
        return RecordKind.IMAGE

    def __init__(self, model: ImageController) -> None:
        settings = StateFields(
            lambda: model.settings, lambda value: setattr(model, "settings", value)
        )
        display = StateFields(
            lambda: model.settings.display,
            lambda value: settings.write(replace(settings.read(), display=value)),
        )
        caches = (
            settings.integer(
                "cpu",
                "CPU window (MiB)",
                lambda s: s.cpu_bytes // 1048576,
                lambda s, v: replace(s, cpu_bytes=v * 1048576),
                1,
                4096,
            ),
            settings.integer(
                "gpu",
                "GPU textures (MiB)",
                lambda s: s.gpu_bytes // 1048576,
                lambda s, v: replace(s, gpu_bytes=v * 1048576),
                1,
                4096,
            ),
            settings.integer(
                "disk",
                "Temporary decoded cache (MiB)",
                lambda s: s.disk_bytes // 1048576,
                lambda s, v: replace(s, disk_bytes=v * 1048576),
                0,
                4096,
            ),
        )
        super().__init__(
            "image-settings",
            (
                ImageChannel(model),
                display.choice(
                    "colormap",
                    "Heatmap colors",
                    tuple(Colormap),
                    lambda s: s.colormap,
                    lambda s, v: replace(s, colormap=v),
                ),
                ImageCoordinates(model),
                Collapsible(
                    "range",
                    "Display range",
                    (
                        DisplayRange(
                            lambda: display.read().value_range,
                            lambda value: display.write(
                                replace(display.read(), value_range=value)
                            ),
                        ),
                    ),
                ),
                Collapsible("caches", "Image caches", caches),
                Collapsible(
                    "annotations",
                    "Annotations",
                    (
                        AnnotationSettings(
                            model.annotation_tools, lambda: model.annotation_column
                        ),
                    ),
                ),
            ),
        )
