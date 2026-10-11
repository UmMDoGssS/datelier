"""Column comparison tabs compose shared plots and complete statistics tables."""

from imgui_bundle import imgui

from datelier.application.comparisons import ComparisonFamily
from datelier.application.comparisons.columns import ColumnComparisonController
from datelier.gui.comparisons.base import ComparisonContent
from datelier.gui.comparisons.tabular.charts import ColumnChart
from datelier.gui.components.layout import FrameContext
from datelier.gui.components.layout.viewport import ResizableViewport
from datelier.gui.components.tables import FactsTable


class ColumnComparisonContent(ComparisonContent):
    def __init__(self, model: ColumnComparisonController) -> None:
        self.model = model
        super().__init__(
            "column-comparison",
            (
                ResizableViewport(
                    "column-viewport",
                    ColumnChart(model),
                    read_height=lambda: model.height,
                    write_height=lambda value: setattr(model, "height", value),
                ),
                FactsTable(
                    "statistics",
                    (
                        "Source",
                        "Column",
                        "Rows",
                        "Included",
                        "Null",
                        "Nonfinite",
                        "Distinct",
                        "Minimum",
                        "Maximum",
                        "Mean",
                        "Stddev",
                        "25%",
                        "Median",
                        "75%",
                        "Mode",
                        "Mode count",
                    ),
                    lambda: model.statistics,
                    170,
                ),
            ),
        )

    @property
    def family(self) -> ComparisonFamily:
        return ComparisonFamily.COLUMNS

    def render(self, frame: FrameContext) -> None:
        imgui.text_wrapped(self.model.message)
        result = self.model.active
        if result:
            imgui.text_wrapped(result.note)
            super().render(frame)
