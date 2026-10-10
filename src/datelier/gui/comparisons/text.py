"""Text comparison subtabs render complete prepared statistics and bounded charts."""

from dataclasses import replace

from imgui_bundle import imgui

from datelier.application.comparisons.base import ComparisonFamily
from datelier.application.comparisons.text import TextComparisonController
from datelier.gui.comparisons.base import ComparisonContent
from datelier.gui.comparisons.text_charts import (
    TextFrequencyComparison,
    TextLengthComparison,
)
from datelier.gui.components.base import FrameContext, Group
from datelier.gui.components.dataframe import DataFrameTable
from datelier.gui.components.facts import FactsTable
from datelier.gui.components.viewport import ResizableViewport, ViewportContent
from datelier.gui.shell.navigation import CanvasTabs, NamedTab


class TextComparisonContent(ComparisonContent):
    def __init__(self, model: TextComparisonController) -> None:
        self.model = model

        def viewport(key: str, chart: ViewportContent) -> ResizableViewport:
            return ResizableViewport(
                key,
                chart,
                read_height=lambda: model.view.height,
                write_height=lambda v: setattr(
                    model, "view", replace(model.view, height=v)
                ),
            )

        super().__init__(
            "text-comparison",
            (
                CanvasTabs(
                    (
                        NamedTab(
                            "Lengths",
                            viewport(
                                "text-length-viewport", TextLengthComparison(model)
                            ),
                        ),
                        NamedTab(
                            "Statistics",
                            Group(
                                "statistics",
                                (
                                    FactsTable(
                                        "statistics",
                                        ("Source", "Column", "Statistic", "Value"),
                                        lambda: model.statistics,
                                        240,
                                    ),
                                    FactsTable(
                                        "lengths",
                                        (
                                            "Source",
                                            "Length",
                                            "Count",
                                            "Mean",
                                            "Std (population)",
                                            "Min",
                                            "25%",
                                            "50%",
                                            "75%",
                                            "95%",
                                            "99%",
                                            "Max",
                                        ),
                                        lambda: model.lengths,
                                        130,
                                    ),
                                ),
                            ),
                        ),
                        NamedTab(
                            "Token frequencies",
                            Group(
                                "frequencies",
                                (
                                    viewport(
                                        "text-frequency-viewport",
                                        TextFrequencyComparison(model),
                                    ),
                                    DataFrameTable(
                                        "all-frequencies",
                                        lambda: (
                                            model.active.frequencies
                                            if model.active
                                            else None
                                        ),
                                    ),
                                ),
                            ),
                        ),
                        NamedTab(
                            "Record outcomes",
                            DataFrameTable(
                                "outcomes",
                                lambda: (
                                    model.active.profiles[model.view.source].records
                                    if model.active
                                    else None
                                ),
                                300,
                            ),
                        ),
                    ),
                    lambda: model.view.tab,
                    lambda v: setattr(model, "view", replace(model.view, tab=v)),
                ),
            ),
        )

    @property
    def family(self) -> ComparisonFamily:
        return ComparisonFamily.TEXT

    def render(self, frame: FrameContext) -> None:
        imgui.text_wrapped(self.model.message)
        result = self.model.active
        if result:
            imgui.text_wrapped(
                f"Exact corpora · shared {result.settings.tokens.mode} tokenizer · "
                f"{result.settings.scale}"
            )
            imgui.text_wrapped(
                "Charts show 12 token types; the frequency table includes the full "
                "vocabulary. Null/failed text is excluded from lengths; empty text "
                "is included. List[Text] elements are separate documents. "
                "Quantiles use linear interpolation."
            )
            for label, p in zip(result.labels, result.profiles, strict=True):
                imgui.text_wrapped(
                    f"{label} / {p.settings.column} · {p.settings.scope.mode} · "
                    f"input SHA-256 {p.input_sha256}"
                )
            super().render(frame)
