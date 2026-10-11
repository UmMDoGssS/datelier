"""Related prepared text charts share viewport, legends and stable source colors."""

from abc import ABC, abstractmethod

import numpy as np
from imgui_bundle import imgui, implot

from datelier.application.comparisons.text import TextComparisonController
from datelier.gui.components.layout import FrameContext
from datelier.gui.components.layout.viewport import ViewportContent
from datelier.gui.components.native import label_text, target
from datelier.gui.profiles.distributions import profile_color
from datelier.inspection.text.comparisons.settings import TextScale
from datelier.inspection.text.comparisons.types import PreparedTextComparison


class TextComparisonChart(ViewportContent, ABC):
    def __init__(self, key: str, model: TextComparisonController) -> None:
        super().__init__(key)
        self.model = model
        self._stamp: tuple[object, ...] = ()

    @abstractmethod
    def axes(self, result: PreparedTextComparison) -> None: ...

    @abstractmethod
    def draw(
        self,
        result: PreparedTextComparison,
        series: int,
        label: str,
        color: imgui.ImVec4,
    ) -> None: ...

    def interact(self, result: PreparedTextComparison, labels: tuple[str, ...]) -> None:
        return

    def render(self, frame: FrameContext) -> None:
        result = self.model.active
        if result is None:
            return
        stamp = (id(result), self.model.view.documents)
        if stamp != self._stamp:
            self._stamp, self.fit = stamp, True
        if self.fit:
            implot.set_next_axes_to_fit()
        if implot.begin_plot("##" + self.key, (-1, self.height)):
            self.axes(result)
            implot.setup_legend(
                implot.Location_.north,
                implot.LegendFlags_.outside | implot.LegendFlags_.horizontal,
            )
            labels = tuple(
                label_text(label) + f"##{p.file_id}"
                for label, p in zip(result.labels, result.profiles, strict=True)
            )
            for i, label in enumerate(labels):
                self.draw(result, i, label, profile_color(result.profiles[i].file_id))
            self.interact(result, labels)
            implot.get_input_map().pan = imgui.MouseButton_.middle
            implot.end_plot()
            target(frame, "canvas")
            self.fit = False

    def close(self) -> None:
        self._stamp = ()
        super().close()


class TextLengthComparison(TextComparisonChart):
    def __init__(self, model: TextComparisonController) -> None:
        super().__init__("text-length-chart", model)

    def axes(self, result: PreparedTextComparison) -> None:
        implot.setup_axes(
            "Counted tokens per document / element",
            "Density"
            if result.settings.scale == TextScale.DENSITY
            else "Documents / elements",
        )

    def draw(
        self,
        result: PreparedTextComparison,
        series: int,
        label: str,
        color: imgui.ImVec4,
    ) -> None:
        implot.plot_line(
            label, result.centers, result.lengths[series], implot.Spec(line_color=color)
        )

    def interact(self, result: PreparedTextComparison, labels: tuple[str, ...]) -> None:
        source = self.model.view.source
        if implot.is_plot_hovered() and implot.internal.get_item(labels[source]).show:
            x = implot.get_plot_mouse_pos().x
            index = int(np.searchsorted(result.edges, x, side="right") - 1)
            if x == result.edges[-1]:
                index = len(result.centers) - 1
            if 0 <= index < len(result.centers):
                imgui.set_tooltip(
                    f"{result.labels[source]} · length bin {index}\n"
                    "Click to select source rows."
                )
                if imgui.is_mouse_clicked(imgui.MouseButton_.left):
                    self.model.select(source, index)


class TextFrequencyComparison(TextComparisonChart):
    def __init__(self, model: TextComparisonController) -> None:
        super().__init__("text-frequency-chart", model)

    def axes(self, result: PreparedTextComparison) -> None:
        implot.setup_axes(
            "Proportion"
            if result.settings.scale == TextScale.DENSITY
            else "Documents / elements"
            if self.model.view.documents
            else "Tokens",
            "Token piece",
            y_flags=implot.AxisFlags_.invert,
        )
        implot.setup_axis_ticks(
            implot.ImAxis_.y1,
            result.frequency_positions.tolist(),
            list(result.frequency_labels),
        )

    def draw(
        self,
        result: PreparedTextComparison,
        series: int,
        label: str,
        color: imgui.ImVec4,
    ) -> None:
        values = (
            result.document_frequencies
            if self.model.view.documents
            else result.token_frequencies
        )
        implot.plot_bars(
            label,
            values[series],
            result.frequency_series_positions[series],
            0.8 / len(result.profiles),
            implot.Spec(flags=implot.BarsFlags_.horizontal, fill_color=color),
        )
