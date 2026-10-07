"""Prepared image statistics, dimension/color plots and complete record outcomes."""

from dataclasses import replace
from typing import TYPE_CHECKING

from imgui_bundle import imgui

from datelier.gui.images.profile_charts import draw_histograms
from datelier.gui.images.profile_tables import record_outcomes, statistics
from datelier.gui.plots.area import PlotArea
from datelier.inspection.images.profile_types import (
    ChannelKey,
    ImageProfile,
    PixelScope,
)
from datelier.inspection.images.settings import ImageProfileViewSettings

if TYPE_CHECKING:
    from datelier.gui.file_session import FileSession


class ImageProfiles:
    def __init__(self) -> None:
        self.area = PlotArea()
        self.shown = self.plot_frames = self.rendered_records = 0
        self.active_tab = "Statistics"
        self._observed: ImageProfileViewSettings | None = None
        self.group_names: tuple[str, ...] = ()

    def show(
        self,
        profile: ImageProfile,
        settings: ImageProfileViewSettings,
        owner: FileSession,
    ) -> ImageProfileViewSettings:
        self.shown += 1
        self.area.height = settings.height
        requested = settings.tab if self._observed != settings else ""
        imgui.text_wrapped(
            f"{profile.settings.column} · {profile.settings.scope.mode} · "
            f"{profile.records.height:,}/{profile.available_records:,} current records"
        )
        imgui.text_wrapped(
            f"{profile.ready:,} decoded · {profile.nulls:,} null · "
            f"{profile.unresolved:,} unresolved (missing/ambiguous) · "
            f"{profile.failures:,} decode failures"
        )
        imgui.text_wrapped(
            f"{profile.profiled_pixels:,}/{profile.total_pixels:,} pixels profiled · "
            + ("sampled" if profile.sampled_pixels else "all original pixels")
        )
        if profile.settings.pixels == PixelScope.SAMPLE:
            imgui.text_wrapped(
                f"Per-image pixel limit {profile.settings.pixel_count:,}; "
                f"seed {profile.settings.pixel_seed}. "
                "Counts describe sampled pixels without extrapolation."
            )
        if imgui.begin_tab_bar("Image profile views"):
            for label in ("Statistics", "Dimensions", "Colors", "Record outcomes"):
                flags = imgui.TabItemFlags_.set_selected if requested == label else 0
                if imgui.begin_tab_item(label, flags=flags)[0]:
                    self.active_tab = label
                    settings = replace(settings, tab=label)
                    if label == "Statistics":
                        imgui.text_wrapped(
                            "Dimensions count images; "
                            "channels count finite pixel values."
                        )
                        statistics(
                            "Original image statistics",
                            (*profile.dimension_summaries, *profile.summaries),
                            max(100, min(290, imgui.get_content_region_avail().y - 35)),
                        )
                        if imgui.collapsing_header("Image statistics details"):
                            imgui.text_wrapped(
                                "Channel means are weighted by pixels. "
                                "Transparent pixels retain stored channels; "
                                "display scales are excluded."
                            )
                    elif label == "Record outcomes":
                        self.rendered_records = record_outcomes(profile, owner)
                    elif label == "Dimensions":
                        settings = self._dimensions(profile, settings)
                    else:
                        settings = self._colors(profile, settings)
                    imgui.end_tab_item()
            imgui.end_tab_bar()
        settings = replace(settings, height=self.area.height)
        self._observed = settings
        return settings

    def _dimensions(
        self, profile: ImageProfile, settings: ImageProfileViewSettings
    ) -> ImageProfileViewSettings:
        names = [chart.label for chart in profile.dimensions]
        choice = names.index(settings.dimension)
        imgui.set_next_item_width(180)
        _, choice = imgui.combo("Image dimension", choice, names)
        settings = replace(settings, dimension=names[choice])
        chart = profile.dimensions[choice]
        if chart.scaled:
            imgui.text_wrapped(
                f"Original bounds {chart.minimum}–{chart.maximum}; axis scaled 0–1."
            )
        if self.area.show(
            "Image distribution",
            (profile.revision, profile.settings, settings.dimension),
            lambda height, fit, axes: draw_histograms(
                (chart,),
                ("Images",),
                "Scaled " + chart.label if chart.scaled else chart.label,
                "Decoded images",
                height,
                fit,
                axes,
            ),
        ):
            self.plot_frames += 1
        return settings

    def _colors(
        self, profile: ImageProfile, settings: ImageProfileViewSettings
    ) -> ImageProfileViewSettings:
        groups = tuple(
            dict.fromkeys((s.key.mode, s.key.dtype) for s in profile.summaries)
        )
        if not groups:
            imgui.text("No decoded channels. Inspect record outcomes for diagnostics.")
            return settings
        current = (settings.group_mode, settings.group_dtype)
        choice = groups.index(current) if current in groups else 0
        self.group_names = tuple(
            ChannelKey(mode, "", dtype).family_label for mode, dtype in groups
        )
        imgui.set_next_item_width(180)
        _, choice = imgui.combo("Channel family", choice, list(self.group_names))
        mode, dtype = groups[choice]
        settings = replace(settings, group_mode=mode, group_dtype=dtype)
        indices = tuple(
            i
            for i, s in enumerate(profile.summaries)
            if (s.key.mode, s.key.dtype) == (mode, dtype)
        )
        charts = tuple(profile.channels[i] for i in indices)
        names = tuple(profile.summaries[i].key.name for i in indices)
        scaled = any(chart.scaled for chart in charts)
        if scaled:
            imgui.text_wrapped(
                "Channels use individual raw bounds below; "
                "axis positions are scaled 0–1."
            )
        if self.area.show(
            "Image distribution",
            (profile.revision, profile.settings, mode, dtype),
            lambda height, fit, axes: draw_histograms(
                charts,
                names,
                "Scaled channel value (0–1)" if scaled else "Original channel value",
                "Profiled pixel values",
                height,
                fit,
                axes,
                scaled,
            ),
            footer=lambda: statistics(
                "Plotted channel statistics",
                tuple(profile.summaries[i] for i in indices),
                110,
            ),
            footer_height=130,
        ):
            self.plot_frames += 1
        return settings
