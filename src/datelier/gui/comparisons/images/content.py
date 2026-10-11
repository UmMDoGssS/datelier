"""Image comparison tabs render prepared curves, statistics and Inspect links."""

from dataclasses import replace

from imgui_bundle import imgui

from datelier.application.comparisons import ComparisonFamily
from datelier.application.comparisons.images import ImageComparisonController
from datelier.gui.comparisons.base import ComparisonContent
from datelier.gui.comparisons.tabular import ComparisonHistogram
from datelier.gui.components.layout import FrameContext
from datelier.gui.components.layout.viewport import ResizableViewport
from datelier.gui.components.tables import DataFrameTable, FactsTable
from datelier.gui.shell.layout import CanvasTabs, NamedTab


class ImageComparisonContent(ComparisonContent):
    def __init__(self, model: ImageComparisonController) -> None:
        self.model = model

        def viewport(key: str) -> ResizableViewport:
            return ResizableViewport(
                key,
                ComparisonHistogram(
                    "image-comparison-chart", lambda: model.plot, model.select_at
                ),
                read_height=lambda: model.view.height,
                write_height=lambda v: setattr(
                    model, "view", replace(model.view, height=v)
                ),
            )

        super().__init__(
            "image-comparison",
            (
                CanvasTabs(
                    (
                        NamedTab("Dimensions", viewport("image-dimension-viewport")),
                        NamedTab("Colors", viewport("image-color-viewport")),
                        NamedTab(
                            "Statistics",
                            FactsTable(
                                "statistics",
                                (
                                    "Source",
                                    "Dimension / channel",
                                    "Values",
                                    "Finite",
                                    "Nonfinite",
                                    "Min",
                                    "Max",
                                    "Mean",
                                    "Stddev",
                                ),
                                lambda: model.statistics,
                                300,
                            ),
                        ),
                        NamedTab(
                            "Records",
                            DataFrameTable(
                                "records",
                                lambda: (
                                    model.active.profiles[model.view.source].records
                                    if model.active
                                    else None
                                ),
                                300,
                                self.open_record,
                            ),
                        ),
                    ),
                    lambda: model.view.tab,
                    lambda v: setattr(model, "view", replace(model.view, tab=v)),
                ),
            ),
        )

    def open_record(self, row: int) -> None:
        result = self.model.active
        if result:
            self.model.open_record(result, self.model.view.source, row)

    @property
    def family(self) -> ComparisonFamily:
        return ComparisonFamily.IMAGES

    def render(self, frame: FrameContext) -> None:
        imgui.text_wrapped(self.model.message)
        result = self.model.active
        if result:
            for label, p in zip(result.labels, result.profiles, strict=True):
                imgui.text_wrapped(
                    f"{label} · {p.settings.column} · {p.settings.scope.mode} · "
                    f"{p.ready}/{p.records.height} ready · "
                    f"{p.profiled_pixels:,}/{p.total_pixels:,} pixels · "
                    f"{p.settings.pixels}"
                )
            imgui.text_wrapped(
                "Colors compare matching mode/dtype families. Samples are counted "
                "without extrapolation; original source values and image dimensions "
                "remain in Statistics."
            )
            super().render(frame)
