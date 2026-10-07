"""Numeric record channel/slice controls derived only from prepared metadata."""

from dataclasses import replace

from imgui_bundle import imgui

from datelier.gui.heatmaps import HeatmapControls
from datelier.inspection.images.types import (
    ImageDisplay,
    ImageLocator,
    ImageMetadata,
    PreparedImage,
)


class RecordHeatmapControls:
    def __init__(self) -> None:
        self.colors = HeatmapControls()

    def show(
        self,
        locator: ImageLocator,
        metadata: ImageMetadata,
        display: ImageDisplay,
        active: PreparedImage | None,
    ) -> ImageDisplay:
        channel = min(metadata.count - 1, display.channel or 0)
        if metadata.count > 1:
            imgui.set_next_item_width(120)
            _, channel = imgui.input_int(
                f"Heatmap channel (0–{metadata.count - 1})", channel
            )
            channel = min(metadata.count - 1, max(0, channel))
        bounds = active.finite_range if active is not None else None
        value_range, colormap = self.colors.show(
            display.value_range, display.colormap, bounds
        )
        display = replace(
            display, channel=channel, value_range=value_range, colormap=colormap
        )
        mapping, catalog = locator.mapping, locator.catalog
        if mapping is not None and catalog is not None:
            shape = catalog.member(mapping.member).shape
            used = (mapping.record_axis, *mapping.display_axes, mapping.channel_axis)
            axes = tuple(i for i in range(len(shape)) if i not in used)
            if axes and imgui.collapsing_header("Heatmap slice"):
                fixed = list(display.fixed or mapping.fixed or (0,) * len(shape))
                if len(fixed) != len(shape):
                    fixed = [0] * len(shape)
                for axis in axes:
                    imgui.set_next_item_width(120)
                    _, fixed[axis] = imgui.input_int(
                        f"Heatmap axis {axis} (0–{shape[axis] - 1})", fixed[axis]
                    )
                    fixed[axis] = max(0, min(shape[axis] - 1, fixed[axis]))
                display = replace(display, fixed=tuple(fixed))
        if active is not None:
            imgui.text_wrapped(
                f"Raw window bounds {active.finite_range}; "
                f"display {active.display_range}."
            )
        else:
            imgui.text("Preparing scalar window…")
        return display
