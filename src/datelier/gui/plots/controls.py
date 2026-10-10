"""Native controls for the injected semantic plot state."""

from imgui_bundle import imgui

from datelier.analysis.types import Algorithm
from datelier.application.plot_settings import PlotState
from datelier.core.dataset import Dataset
from datelier.gui.widgets.fields import combo
from datelier.inspection.exploration import Explorer


class PlotControls(PlotState):
    def show(self, explorer: Explorer, dataset: Dataset | None) -> None:
        if dataset is None or not imgui.collapsing_header("Plot settings"):
            return
        _, self.bins = imgui.slider_int("Histogram bins", self.bins, 1, 100)
        _, self.top_counts = imgui.slider_int("Top counts", self.top_counts, 1, 100)
        _, self.correlation_columns = imgui.slider_int(
            "Correlation columns", self.correlation_columns, 2, 16
        )
        _, self.point_limit = imgui.slider_int(
            "Scatter points", self.point_limit, 1, 10_000
        )
        if imgui.tree_node("Distribution settings"):
            _, self.standardize = imgui.checkbox("Z-score plots", self.standardize)
            _, self.density = imgui.checkbox("Histogram density", self.density)
            _, self.bandwidth = imgui.slider_float(
                "KDE bandwidth", self.bandwidth, 0.1, 5
            )
            _, self.seed = imgui.input_int("Distribution seed", self.seed)
            imgui.tree_pop()
        if imgui.button("Apply plot settings"):
            try:
                settings = self.settings()
                if (
                    settings.scatter_pair
                    and settings.scatter_pair[0] == settings.scatter_pair[1]
                ):
                    raise ValueError("Choose two distinct scatter columns.")
                explorer.request(dataset, settings)
                self.error = ""
            except ValueError as error:
                self.error = str(error)
        imgui.same_line()
        if imgui.button("Abandon exploration"):
            explorer.abandon()
        if self.error:
            imgui.text_wrapped(self.error)

    def show_axes(self, explorer: Explorer, dataset: Dataset) -> None:
        if len(self.numeric) < self.scatter_dimensions:
            imgui.text_wrapped(
                f"{self.scatter_dimensions}D column axes require "
                f"{self.scatter_dimensions} numeric features."
            )
            return
        changed = self.scatter_dirty
        axes = ["x_index", "y_index"] + (["z_index"] if self.three_d else [])
        for col, attr in enumerate(axes):
            picked, index = combo("XYZ"[col], getattr(self, attr), list(self.numeric))
            if picked:
                self.choose_axis(attr, index)
                changed = True
        if changed:
            self.scatter_dirty = False
            self.custom_scatter = True
            try:
                if self.x_index == self.y_index:
                    raise ValueError("Choose distinct raw axes")
                if self.three_d and (
                    len(self.numeric) < 3
                    or self.z_index in (self.x_index, self.y_index)
                ):
                    raise ValueError("Choose three distinct numeric raw axes")
                explorer.request(dataset, self.settings())
                self.error = ""
            except ValueError as error:
                self.error = str(error)
        if self.error:
            imgui.text_wrapped(self.error)

    def show_color(self) -> bool:
        choices = [
            "Uniform",
            "Column",
            *(a.value for a in Algorithm if a.is_clustering),
        ]
        changed, index = combo("Colors", choices.index(self.color_source), choices)
        if changed:
            self.choose_color(choices[index])
        if self.color_source == "Column":
            if self.color_columns:
                picked, index = combo(
                    "Color column",
                    max(0, self.color_index - 1),
                    list(self.color_columns),
                )
                self.color_index = index + 1
                self.scatter_dirty |= picked
                changed |= picked
            else:
                imgui.text("No supported color columns")
        return changed
