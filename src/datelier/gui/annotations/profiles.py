"""Exact prepared box class/quality tables, size charts and linked records."""

from dataclasses import replace
from typing import TYPE_CHECKING

from imgui_bundle import imgui

from datelier.gui.annotations.outcomes import box_records, open_rows
from datelier.gui.images.profile_charts import draw_histograms
from datelier.gui.images.profile_tables import statistics
from datelier.gui.plots.area import PlotArea
from datelier.inspection.annotations.profile_types import (
    AnnotationProfile,
    AnnotationProfiles,
)
from datelier.inspection.annotations.view_settings import AnnotationViewSettings
from datelier.plotting.selection import SELECTION_LIMIT

if TYPE_CHECKING:
    from datelier.gui.file_session import FileSession


class AnnotationProfilesView:
    def __init__(self) -> None:
        self._observed: AnnotationViewSettings | None = None
        self.plot_frames = 0
        self.area = PlotArea()
        self.area.height = 100

    def show(
        self, owner: FileSession, settings: AnnotationViewSettings
    ) -> AnnotationViewSettings:
        _, bins = imgui.input_int("Annotation histogram bins", settings.bins)
        settings = replace(settings, bins=max(1, min(256, bins)))
        owner.images.settings = replace(owner.images.settings, annotation_view=settings)
        owner.images.sync(owner)
        jobs = owner.images.annotation_profiles
        if imgui.button("Prepare annotation profiles"):
            try:
                jobs.request()
            except ValueError as error:
                jobs.message = str(error)
        if jobs.busy:
            imgui.same_line()
            if imgui.button("Abandon annotation profiles"):
                jobs.abandon()
                jobs.message = "Profiling abandoned; executing work is winding down."
            phase, done, total = jobs.progress.value
            imgui.text(f"{phase} · {done:,}/{total:,}")
        imgui.text_wrapped(jobs.message)
        result = jobs.active
        if result is None:
            return settings
        names = [
            source.recipe.name or f"Source {index + 1}"
            for index, source in enumerate(result.annotations.sources)
        ]
        ids = [source.source_id for source in result.sources]
        if not ids:
            return settings
        current = ids.index(settings.source_id) if settings.source_id in ids else 0
        _, current = imgui.combo("Profile annotation source", current, names)
        settings = replace(settings, source_id=ids[current])
        profile = result.sources[current]
        requested = settings.profile_tab if self._observed != settings else ""
        if imgui.begin_child(
            "Annotation profile results", (0, 260), imgui.ChildFlags_.borders
        ):
            if imgui.begin_tab_bar("Annotation profile views"):
                for label in ("Classes", "Sizes", "Quality", "Boxes"):
                    flags = (
                        imgui.TabItemFlags_.set_selected if requested == label else 0
                    )
                    if imgui.begin_tab_item(label, flags=flags)[0]:
                        settings = replace(settings, profile_tab=label)
                        if label == "Classes":
                            classes(profile, result, owner)
                        elif label == "Quality":
                            quality(profile)
                        elif label == "Boxes":
                            box_records(result.annotations.sources[current], owner)
                        else:
                            settings = self._sizes(profile, settings)
                        imgui.end_tab_item()
                imgui.end_tab_bar()
        imgui.end_child()
        self._observed = settings
        return settings

    def _sizes(
        self, profile: AnnotationProfile, settings: AnnotationViewSettings
    ) -> AnnotationViewSettings:
        names = [chart.label for chart in profile.distributions]
        _, current = imgui.combo(
            "Box size distribution", names.index(settings.distribution), names
        )
        settings = replace(settings, distribution=names[current])
        chart = profile.distributions[current]
        statistics("Box size statistics", profile.summaries, 90)
        if chart.scaled:
            imgui.text(
                f"Original bounds {chart.minimum}–{chart.maximum}; scaled axis 0–1."
            )
        if self.area.show(
            "Box distribution",
            (id(profile), settings.distribution),
            lambda height, fit, axes: draw_histograms(
                (chart,), ("Boxes",), chart.label, "Associated boxes", height, fit, axes
            ),
        ):
            self.plot_frames += 1
        return settings


def classes(
    profile: AnnotationProfile, result: AnnotationProfiles, owner: FileSession
) -> None:
    flags = (
        imgui.TableFlags_.borders
        | imgui.TableFlags_.row_bg
        | imgui.TableFlags_.scroll_y
    )
    if imgui.begin_table("Annotation class counts", 3, flags, (-1, 210)):
        for name in ("Class", "Original ID", "Associated boxes"):
            imgui.table_setup_column(name)
        imgui.table_headers_row()
        clipper = imgui.ListClipper()
        clipper.begin(len(profile.classes))
        while clipper.step():
            for index in range(clipper.display_start, clipper.display_end):
                item = profile.classes[index]
                imgui.push_id(index)
                imgui.table_next_row()
                imgui.table_next_column()
                if imgui.selectable(item.name, False)[0]:
                    open_rows(owner, result.annotations, item.row_ids)
                imgui.table_next_column()
                imgui.text_unformatted(str(item.id))
                imgui.table_next_column()
                imgui.text_unformatted(str(item.count))
                if len(item.row_ids) > SELECTION_LIMIT:
                    imgui.text_wrapped(
                        f"Links first {SELECTION_LIMIT:,}/{len(item.row_ids):,} images."
                    )
                imgui.pop_id()
        imgui.end_table()


def quality(profile: AnnotationProfile) -> None:
    flags = (
        imgui.TableFlags_.borders
        | imgui.TableFlags_.row_bg
        | imgui.TableFlags_.scroll_y
    )
    if imgui.begin_table("Annotation quality counts", 2, flags, (-1, 210)):
        imgui.table_setup_column("Outcome")
        imgui.table_setup_column("Count")
        imgui.table_headers_row()
        clipper = imgui.ListClipper()
        clipper.begin(len(profile.quality))
        while clipper.step():
            for index in range(clipper.display_start, clipper.display_end):
                label, count = profile.quality[index]
                imgui.table_next_row()
                imgui.table_next_column()
                imgui.text_unformatted(label)
                imgui.table_next_column()
                imgui.text_unformatted(str(count))
        imgui.end_table()
