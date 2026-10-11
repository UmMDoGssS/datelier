"""Image profile subtabs compose shared statistics, charts and record tables."""

from collections.abc import Callable
from dataclasses import replace

from imgui_bundle import imgui

from datelier.application.images import ImageController
from datelier.application.profiles import ProfileFamily
from datelier.gui.components.base import FrameContext
from datelier.gui.components.dataframe import DataFrameTable
from datelier.gui.components.facts import FactsTable
from datelier.gui.components.viewport import ResizableViewport
from datelier.gui.profiles.base import ProfileContent
from datelier.gui.profiles.histograms import HistogramContent
from datelier.gui.shell.navigation import CanvasTabs, NamedTab
from datelier.inspection.images.profiles import ImageHistogram, PixelScope


class ImageProfileContent(ProfileContent):
    def __init__(
        self, model: ImageController, open_record: Callable[[int], None]
    ) -> None:
        self.model = model

        def viewport(key: str, content: HistogramContent) -> ResizableViewport:
            return ResizableViewport(
                key,
                content,
                read_height=lambda: model.settings.profile_view.height,
                write_height=lambda value: setattr(
                    model,
                    "settings",
                    replace(
                        model.settings,
                        profile_view=replace(model.settings.profile_view, height=value),
                    ),
                ),
            )

        super().__init__(
            "image-profile",
            (
                CanvasTabs(
                    (
                        NamedTab(
                            "Statistics",
                            FactsTable(
                                "image-statistics",
                                (
                                    "Dimension / channel",
                                    "Values",
                                    "Finite",
                                    "Nonfinite",
                                    "Minimum",
                                    "Maximum",
                                    "Mean",
                                    "Stddev",
                                ),
                                lambda: model.statistics,
                                300,
                            ),
                        ),
                        NamedTab(
                            "Dimensions",
                            viewport(
                                "dimensions",
                                HistogramContent(
                                    "dimension-chart",
                                    self.dimensions,
                                    lambda: model.settings.profile_view.dimension,
                                    "Decoded images",
                                ),
                            ),
                        ),
                        NamedTab(
                            "Colors",
                            viewport(
                                "colors",
                                HistogramContent(
                                    "channel-chart",
                                    self.channels,
                                    lambda: "Original channel value",
                                    "Profiled pixel values",
                                ),
                            ),
                        ),
                        NamedTab(
                            "Record outcomes",
                            DataFrameTable(
                                "record-outcomes",
                                lambda: (
                                    model.profile_jobs.active.records
                                    if model.profile_jobs.active
                                    else None
                                ),
                                300,
                                open_record,
                            ),
                        ),
                    ),
                    lambda: model.settings.profile_view.tab,
                    lambda value: setattr(
                        model,
                        "settings",
                        replace(
                            model.settings,
                            profile_view=replace(
                                model.settings.profile_view, tab=value
                            ),
                        ),
                    ),
                ),
            ),
        )

    @property
    def family(self) -> ProfileFamily:
        return ProfileFamily.IMAGES

    def dimensions(self) -> tuple[ImageHistogram, ...]:
        profile = self.model.profile_jobs.active
        return (
            tuple(
                chart
                for chart in profile.dimensions
                if chart.label == self.model.settings.profile_view.dimension
            )
            if profile
            else ()
        )

    def channels(self) -> tuple[ImageHistogram, ...]:
        profile, view = self.model.profile_jobs.active, self.model.settings.profile_view
        if profile is None:
            return ()
        chosen = (view.group_mode, view.group_dtype)
        group = (
            chosen
            if chosen in self.model.channel_groups
            else next(iter(self.model.channel_groups), None)
        )
        return tuple(
            chart
            for chart, summary in zip(profile.channels, profile.summaries, strict=True)
            if (summary.key.mode, summary.key.dtype) == group
        )

    def render(self, frame: FrameContext) -> None:
        model = self.model
        imgui.text_wrapped(model.profile_jobs.message)
        profile = model.profile_jobs.active
        if profile is None:
            return
        imgui.text_wrapped(
            f"{profile.settings.column} · {profile.settings.scope.mode} · "
            f"{profile.records.height:,}/{profile.available_records:,} current records"
        )
        imgui.text_wrapped(
            f"{profile.profiled_pixels:,}/{profile.total_pixels:,} pixels profiled. "
            "Dimension statistics count images; "
            "channels retain original values and pixel weighting."
        )
        if profile.settings.pixels == PixelScope.SAMPLE:
            imgui.text_wrapped(
                f"Per-image pixel limit {profile.settings.pixel_count:,}; seed "
                f"{profile.settings.pixel_seed}. Sample counts are not extrapolated."
            )
        super().render(frame)
