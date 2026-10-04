"""Plot settings with explicit bounds and whole-schema column choices."""

from dataclasses import dataclass, field

from imgui_bundle import imgui

from datelier.dataset import Dataset
from datelier.distributions import DistributionSettings
from datelier.exploration import Explorer, PlotSettings
from datelier.plotting import numeric_columns
from datelier.profiling import ProfileKind, profile_kind


@dataclass
class PlotControls:
    profile_columns: int = 32
    bins: int = 20
    top_counts: int = 12
    correlation_columns: int = 8
    point_limit: int = 2_000
    custom_scatter: bool = False
    x_index: int = 0
    y_index: int = 1
    profile_index: int = 0
    columns: tuple[str, ...] = ()
    numeric: tuple[str, ...] = ()
    error: str = ""
    compare_columns: list[str] = field(default_factory=list)
    standardize: bool = False
    density: bool = True
    bandwidth: float = 1.0
    seed: int = 42
    color_index: int = 0
    color_columns: tuple[str, ...] = ()
    relationship_features: list[str] | None = None

    def bind(self, dataset: Dataset) -> None:
        previous_x = self.numeric[self.x_index] if self.numeric else ""
        previous_y = self.numeric[self.y_index] if self.numeric else ""
        previous_profile = (
            self.columns[self.profile_index - 1] if self.profile_index else ""
        )
        previous_color = (
            self.color_columns[self.color_index - 1] if self.color_index else ""
        )
        self.columns = tuple(dataset.table.columns)
        self.color_columns = tuple(
            n
            for n, t in dataset.table.schema.items()
            if profile_kind(t) != ProfileKind.UNSUPPORTED
        )
        self.color_index = (
            self.color_columns.index(previous_color) + 1
            if previous_color in self.color_columns
            else 0
        )
        self.numeric = numeric_columns(dataset)
        self.relationship_features = (
            list(self.numeric[:6])
            if self.relationship_features is None
            else [n for n in self.relationship_features if n in self.numeric]
        )
        self.compare_columns = [n for n in self.compare_columns if n in self.numeric]
        self.x_index = (
            self.numeric.index(previous_x) if previous_x in self.numeric else 0
        )
        self.y_index = (
            self.numeric.index(previous_y)
            if previous_y in self.numeric
            else max(0, min(1, len(self.numeric) - 1))
        )
        self.profile_index = (
            self.columns.index(previous_profile) + 1
            if previous_profile in self.columns
            else 0
        )
        if (
            len(self.numeric) < 2
            or previous_x not in self.numeric
            or previous_y not in self.numeric
            or self.x_index == self.y_index
        ):
            self.custom_scatter = False

    def settings(self) -> PlotSettings:
        pair = (
            (self.numeric[self.x_index], self.numeric[self.y_index])
            if self.custom_scatter
            else None
        )
        return PlotSettings(
            self.profile_columns,
            self.bins,
            self.top_counts,
            self.correlation_columns,
            self.point_limit,
            pair,
            self.columns[self.profile_index - 1] if self.profile_index else None,
            DistributionSettings(
                tuple(self.compare_columns),
                self.standardize,
                self.density,
                self.bandwidth,
                self.seed,
            ),
            self.color_columns[self.color_index - 1] if self.color_index else None,
            tuple(self.relationship_features or ()),
        )

    def show(self, explorer: Explorer, dataset: Dataset | None) -> None:
        if dataset is None or not imgui.collapsing_header("Plot settings"):
            return
        _, self.profile_columns = imgui.slider_int(
            "Profile columns", self.profile_columns, 1, 128
        )
        _, self.bins = imgui.slider_int("Histogram bins", self.bins, 1, 100)
        _, self.top_counts = imgui.slider_int("Top counts", self.top_counts, 1, 100)
        _, self.correlation_columns = imgui.slider_int(
            "Correlation columns", self.correlation_columns, 2, 16
        )
        _, self.point_limit = imgui.slider_int(
            "Scatter points", self.point_limit, 1, 10_000
        )
        _, self.profile_index = imgui.combo(
            "Profile focus", self.profile_index, ["Leading columns", *self.columns]
        )
        imgui.text_wrapped(
            "Choose any column for a focused profile. Correlations use at most "
            "120 pairs and 10,000 input rows. Counts use at most 100,000 input rows."
        )
        if imgui.tree_node("Numeric comparisons (up to eight columns)"):
            for name in self.numeric:
                chosen = name in self.compare_columns
                imgui.begin_disabled(not chosen and len(self.compare_columns) >= 8)
                changed, checked = imgui.checkbox(name + "##comparison", chosen)
                imgui.end_disabled()
                if changed:
                    if checked:
                        self.compare_columns.append(name)
                    else:
                        self.compare_columns.remove(name)
            _, self.standardize = imgui.checkbox("Z-score comparison", self.standardize)
            _, self.density = imgui.checkbox("Histogram density", self.density)
            _, self.bandwidth = imgui.slider_float(
                "KDE bandwidth", self.bandwidth, 0.1, 5
            )
            _, self.seed = imgui.input_int("Comparison seed", self.seed)
            imgui.tree_pop()
        if imgui.tree_node(
            "Relationship features (grid up to eight, heatmap up to 16)"
        ):
            features = self.relationship_features or []
            for name in self.numeric:
                chosen = name in features
                imgui.begin_disabled(not chosen and len(features) >= 16)
                changed, checked = imgui.checkbox(name + "##relationship", chosen)
                imgui.end_disabled()
                if changed:
                    if checked:
                        features.append(name)
                    else:
                        features.remove(name)
            self.relationship_features = features
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
        if len(self.numeric) < 2:
            imgui.text("Scatter requires at least two numeric columns.")
            return
        imgui.set_next_item_width(160)
        _, self.x_index = imgui.combo("Raw X", self.x_index, list(self.numeric))
        imgui.same_line()
        imgui.set_next_item_width(160)
        _, self.y_index = imgui.combo("Raw Y", self.y_index, list(self.numeric))
        imgui.set_next_item_width(160)
        _, self.color_index = imgui.combo(
            "Color column", self.color_index, ["Uniform", *self.color_columns]
        )
        imgui.same_line()
        if imgui.button("Update raw scatter"):
            self.custom_scatter = True
            try:
                if self.x_index == self.y_index:
                    raise ValueError("Choose distinct raw axes")
                explorer.request(dataset, self.settings())
                self.error = ""
            except ValueError as error:
                self.error = str(error)
        if self.error:
            imgui.text_wrapped(self.error)
