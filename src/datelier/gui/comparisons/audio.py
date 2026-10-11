"""Audio comparisons reuse histogram/table views without owning listening state."""

from dataclasses import replace

from imgui_bundle import imgui

from datelier.application.comparisons.audio import AudioComparisonController
from datelier.application.comparisons.base import ComparisonFamily
from datelier.gui.comparisons.base import ComparisonContent
from datelier.gui.comparisons.histograms import ComparisonHistogram
from datelier.gui.components.base import FrameContext, Group
from datelier.gui.components.dataframe import DataFrameTable
from datelier.gui.components.facts import FactsTable
from datelier.gui.components.viewport import ResizableViewport
from datelier.gui.shell.navigation import CanvasTabs, NamedTab


class AudioComparisonContent(ComparisonContent):
    def __init__(self, model: AudioComparisonController) -> None:
        self.model = model
        super().__init__(
            "audio-comparison",
            (
                CanvasTabs(
                    (
                        NamedTab(
                            "Distributions",
                            ResizableViewport(
                                "audio-comparison-viewport",
                                ComparisonHistogram(
                                    "audio-comparison-chart",
                                    lambda: model.plot,
                                    model.select_at,
                                ),
                                read_height=lambda: model.view.height,
                                write_height=lambda v: setattr(
                                    model, "view", replace(model.view, height=v)
                                ),
                            ),
                        ),
                        NamedTab(
                            "Statistics",
                            Group(
                                "statistics",
                                (
                                    FactsTable(
                                        "metric-summary",
                                        (
                                            "Source",
                                            "Metric / units",
                                            "Values",
                                            "Min",
                                            "Max",
                                            "Mean",
                                        ),
                                        lambda: model.statistics,
                                        140,
                                    ),
                                    DataFrameTable(
                                        "channels",
                                        lambda: (
                                            model.active.profiles[
                                                model.view.source
                                            ].channel_records
                                            if model.active
                                            else None
                                        ),
                                        220,
                                    ),
                                ),
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
        return ComparisonFamily.AUDIO

    def render(self, frame: FrameContext) -> None:
        imgui.text_wrapped(self.model.message)
        result = self.model.active
        if result:
            for label, p in zip(result.labels, result.profiles, strict=True):
                imgui.text_wrapped(
                    f"{label} · {p.settings.column} · {p.settings.scope.mode} · "
                    f"{p.ready}/{p.records.height} ready · {p.settings.mode}"
                )
            imgui.text_wrapped(
                "Original rates and amplitude units are preserved. Fractions use "
                "each source’s saved clipping/silence thresholds. "
                "Header profiles do not decode signals."
            )
            super().render(frame)
