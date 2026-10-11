"""Exact annotation profiles use shared virtual tables and resizable charts."""

from collections.abc import Callable
from dataclasses import replace

from imgui_bundle import imgui

from datelier.application.annotations import AnnotationController
from datelier.gui.components.layout import Container, FrameContext, Group
from datelier.gui.components.layout.viewport import ResizableViewport
from datelier.gui.components.tables import DataFrameTable, FactsTable, SequenceTable
from datelier.gui.profiles.distributions import HistogramContent
from datelier.gui.shell.layout import CanvasTabs, NamedTab
from datelier.inspection.annotations.association import AssociatedBox


class AnnotationProfileContent(Container):
    def __init__(
        self,
        model: AnnotationController,
        open_rows: Callable[[tuple[int, ...]], None],
        select: Callable[[AssociatedBox], None],
    ) -> None:
        self.model, self.open_rows, self.select = model, open_rows, select
        super().__init__(
            "annotation-profiles",
            (
                CanvasTabs(
                    (
                        NamedTab(
                            "Classes",
                            SequenceTable(
                                "classes",
                                ("ID", "Class", "Boxes", "Images"),
                                lambda: model.profile.classes if model.profile else (),
                                lambda item: (
                                    item.id,
                                    item.name,
                                    item.count,
                                    len(item.row_ids),
                                ),
                                220,
                                self.open_class,
                            ),
                        ),
                        NamedTab(
                            "Sizes",
                            Group(
                                "sizes",
                                (
                                    ResizableViewport(
                                        "box-size",
                                        HistogramContent(
                                            "size-chart",
                                            model.distributions,
                                            lambda: model.read_view().distribution,
                                            "Associated boxes",
                                        ),
                                        read_height=lambda: model.read_view().height,
                                        write_height=lambda value: model.write_view(
                                            replace(model.read_view(), height=value)
                                        ),
                                    ),
                                    SequenceTable(
                                        "size-statistics",
                                        (
                                            "Measure",
                                            "Values",
                                            "Finite",
                                            "Nonfinite",
                                            "Minimum",
                                            "Maximum",
                                            "Mean",
                                            "Stddev",
                                        ),
                                        lambda: (
                                            model.profile.summaries
                                            if model.profile
                                            else ()
                                        ),
                                        lambda s: (
                                            s.key.name,
                                            s.values,
                                            s.finite,
                                            s.nonfinite,
                                            s.minimum,
                                            s.maximum,
                                            s.mean,
                                            s.stddev,
                                        ),
                                        130,
                                    ),
                                ),
                            ),
                        ),
                        NamedTab(
                            "Quality",
                            FactsTable(
                                "quality",
                                ("Outcome", "Count"),
                                lambda: model.profile.quality if model.profile else (),
                                260,
                            ),
                        ),
                        NamedTab(
                            "Boxes",
                            DataFrameTable(
                                "profile-boxes",
                                lambda: (
                                    model.profile.records if model.profile else None
                                ),
                                260,
                                self.open_box,
                            ),
                        ),
                    ),
                    lambda: model.read_view().profile_tab,
                    lambda value: model.write_view(
                        replace(model.read_view(), profile_tab=value)
                    ),
                ),
            ),
        )

    def open_class(self, index: int) -> None:
        profile = self.model.profile
        if profile:
            self.open_rows(profile.classes[index].row_ids)

    def open_box(self, index: int) -> None:
        profile, source = self.model.profile, self.model.source
        if profile and source:
            box_index = int(profile.records["box_index"][index])
            self.select(source.boxes[box_index])

    def render(self, frame: FrameContext) -> None:
        imgui.text_wrapped(self.model.profiles.message)
        if self.model.profile:
            imgui.text_wrapped(
                "Exact original-box counts and geometry; "
                "overlays do not change profile statistics."
            )
            super().render(frame)
