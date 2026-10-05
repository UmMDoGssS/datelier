"""Plot settings with explicit bounds and whole-schema column choices."""

from dataclasses import dataclass, field

from imgui_bundle import imgui

from datelier.analysis_types import Algorithm, ClusteringResult
from datelier.category_charts import CategoryRepresentation, CategorySettings
from datelier.column_roles import ColumnRole
from datelier.dataset import Dataset
from datelier.distributions import DistributionSettings
from datelier.exploration import Explorer, PlotSettings
from datelier.gui_fields import combo
from datelier.plotting import feature_columns


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
    color_source: str = "Uniform"
    cluster_result: ClusteringResult | None = None
    three_d: bool = False
    z_index: int = 2
    scatter_dirty: bool = False
    relationship_chart: str = "Scatter"
    categories: tuple[str, ...] = ()
    category_column: str | None = None
    category_group: str | None = None
    category_value: str | None = None
    diagonal_mode: int = 0

    def bind(self, dataset: Dataset) -> None:
        self.scatter_dirty = False
        self.cluster_result = None
        previous_x = self.numeric[self.x_index] if self.numeric else ""
        previous_y = self.numeric[self.y_index] if self.numeric else ""
        previous_z = (
            self.numeric[min(self.z_index, len(self.numeric) - 1)]
            if self.numeric
            else ""
        )
        previous_profile = (
            self.columns[self.profile_index - 1] if self.profile_index else ""
        )
        previous_color = (
            self.color_columns[self.color_index - 1] if self.color_index else ""
        )
        self.columns = tuple(dataset.table.columns)
        self.color_columns = tuple(
            info.name
            for info in dataset.roles or ()
            if info.role
            in (ColumnRole.NUMERIC, ColumnRole.CATEGORY, ColumnRole.TEMPORAL)
        )
        self.color_index = (
            self.color_columns.index(previous_color) + 1
            if previous_color in self.color_columns
            else int(self.color_source == "Column" and bool(self.color_columns))
        )
        self.numeric = feature_columns(dataset)
        self.categories = dataset.columns_for(ColumnRole.CATEGORY)
        self.category_column = (
            self.category_column
            if self.category_column in self.categories
            else min(
                self.categories,
                key=lambda name: dataset.role(name).distinct or 0,
            )
            if self.categories
            else None
        )
        self.category_group = (
            self.category_group
            if self.category_group in self.categories
            and self.category_group != self.category_column
            else next((n for n in self.categories if n != self.category_column), None)
        )
        self.category_value = (
            self.category_value
            if self.category_value in self.numeric
            else next(iter(self.numeric), None)
        )
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
        self.z_index = (
            self.numeric.index(previous_z)
            if previous_z in self.numeric
            else max(0, min(2, len(self.numeric) - 1))
        )
        if len(self.numeric) >= 2 and self.y_index == self.x_index:
            self.y_index = next(
                i for i in range(len(self.numeric)) if i != self.x_index
            )
        if len(self.numeric) >= 3 and self.z_index in (self.x_index, self.y_index):
            self.z_index = next(
                i
                for i in range(len(self.numeric))
                if i not in (self.x_index, self.y_index)
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
            if self.custom_scatter or self.three_d and len(self.numeric) >= 3
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
            self.color_column,
            tuple(self.relationship_features or ()),
            self.cluster_result if self.cluster_color else None,
            self.numeric[self.z_index]
            if self.three_d and len(self.numeric) >= 3
            else None,
            self.category_settings(),
            self.diagonal_mode,
        )

    def category_settings(self) -> CategorySettings | None:
        if self.relationship_chart == "Scatter" or self.category_column is None:
            return None
        mode = CategoryRepresentation(self.relationship_chart)
        return CategorySettings(
            self.category_column,
            mode,
            self.category_value
            if mode
            not in (CategoryRepresentation.COUNTS, CategoryRepresentation.GROUPED)
            else None,
            self.category_group if mode == CategoryRepresentation.GROUPED else None,
            min(30, self.top_counts),
        )

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
        if len(self.numeric) < 2:
            imgui.text("Scatter requires at least two numeric columns.")
            return
        changed = self.scatter_dirty
        axes = ["x_index", "y_index"] + (["z_index"] if self.three_d else [])
        if imgui.begin_table(
            "Scatter axes", len(axes), imgui.TableFlags_.sizing_stretch_same
        ):
            imgui.table_next_row()
            for col, attr in enumerate(axes):
                imgui.table_set_column_index(col)
                current = getattr(self, attr)
                picked, index = combo(
                    "XYZ"[col],
                    current,
                    list(self.numeric),
                )
                if picked:
                    self.choose_axis(attr, index)
                    changed = True
            imgui.end_table()
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

    def show_dimensions(self) -> None:
        changed, dimensions = combo(
            "Dimensions",
            int(self.three_d and len(self.numeric) >= 3),
            ["2D", "3D"] if len(self.numeric) >= 3 else ["2D"],
        )
        self.three_d = dimensions == 1
        if (
            changed
            and self.three_d
            and len(self.numeric) >= 3
            and self.z_index in (self.x_index, self.y_index)
        ):
            self.z_index = next(
                i
                for i in range(len(self.numeric))
                if i not in (self.x_index, self.y_index)
            )
        if changed:
            self.scatter_dirty = True

    @property
    def cluster_algorithm(self) -> Algorithm | None:
        return next(
            (a for a in Algorithm if a.is_clustering and a.value == self.color_source),
            None,
        )

    @property
    def cluster_color(self) -> bool:
        return self.cluster_algorithm is not None

    @property
    def color_column(self) -> str | None:
        if self.color_source == "Column" and self.color_index:
            return self.color_columns[self.color_index - 1]
        return None

    def choose_color(self, source: str) -> None:
        choices = [
            "Uniform",
            "Column",
            *(a.value for a in Algorithm if a.is_clustering),
        ]
        if source not in choices:
            raise ValueError("Unknown color source")
        if source != self.color_source:
            self.color_source = source
            self.cluster_result = None
            self.scatter_dirty = True
        if source == "Column" and not self.color_index and self.color_columns:
            self.color_index = 1

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

    def choose_axis(self, attr: str, index: int) -> None:
        """Swap an occupied axis so two-column datasets can reverse X and Y."""
        axes = ["x_index", "y_index"] + (["z_index"] if self.three_d else [])
        previous = getattr(self, attr)
        for other in axes:
            if other != attr and getattr(self, other) == index:
                setattr(self, other, previous)
        setattr(self, attr, index)
