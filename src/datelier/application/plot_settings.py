"""Semantic plot drafts, separate from native control rendering."""

from dataclasses import dataclass, field

from datelier.analysis.types import Algorithm, ClusteringResult
from datelier.core.column_roles import ColumnRole
from datelier.core.dataset import Dataset
from datelier.inspection.exploration import PlotSettings
from datelier.plotting.categories import CategoryRepresentation, CategorySettings
from datelier.plotting.data import feature_columns
from datelier.plotting.distributions import DistributionSettings


@dataclass
class PlotState:
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
    profile_redirect: str | None = None

    @property
    def chart_choice(self) -> str:
        if self.relationship_chart == "Scatter":
            return "Scatter 3D" if self.three_d else "Scatter 2D"
        return self.relationship_chart

    @property
    def scatter_dimensions(self) -> int:
        return 3 if self.three_d else 2

    @property
    def chart_choices(self) -> tuple[str, ...]:
        choices = ["Scatter 2D"]
        if self.categories:
            choices.append(CategoryRepresentation.COUNTS.value)
            if len(self.categories) > 1:
                choices.append(CategoryRepresentation.GROUPED.value)
            if self.numeric:
                choices.extend(
                    m.value
                    for m in CategoryRepresentation
                    if m
                    not in (
                        CategoryRepresentation.COUNTS,
                        CategoryRepresentation.GROUPED,
                    )
                )
        return tuple(choices)

    def choose_category(self, name: str) -> None:
        if name not in self.categories:
            return
        self.category_column = name
        if self.category_group == name:
            self.category_group = next((n for n in self.categories if n != name), None)

    def choose_chart(self, chart: str) -> None:
        if chart in ("Scatter 2D", "Scatter 3D"):
            three_d = chart == "Scatter 3D"
            self.scatter_dirty |= self.three_d != three_d
            self.three_d = three_d
            self.relationship_chart = "Scatter"
            if len(self.numeric) >= 3 and self.z_index in (self.x_index, self.y_index):
                self.z_index = next(
                    i
                    for i in range(len(self.numeric))
                    if i not in (self.x_index, self.y_index)
                )
        else:
            self.relationship_chart = CategoryRepresentation(chart).value

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
        if (
            self.relationship_chart != "Scatter"
            and self.chart_choice not in self.chart_choices
        ):
            self.choose_chart("Scatter 2D")
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
            self.bandwidth,
            self.seed,
        )

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

    def choose_axis(self, attr: str, index: int) -> None:
        """Swap an occupied axis so two-column datasets can reverse X and Y."""
        axes = ["x_index", "y_index"] + (["z_index"] if self.three_d else [])
        previous = getattr(self, attr)
        for other in axes:
            if other != attr and getattr(self, other) == index:
                setattr(self, other, previous)
        setattr(self, attr, index)
