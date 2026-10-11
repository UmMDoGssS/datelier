"""Coordinate, color and correlation drafts use independent column pickers."""

from collections.abc import Callable

from datelier.application.columns import ColumnChoice, MultiSelection, SingleSelection
from datelier.application.plot_settings import PlotState
from datelier.gui.components.actions import JobFeedback, JobSnapshot
from datelier.gui.components.base import Container
from datelier.gui.components.columns import ColumnPicker
from datelier.gui.components.fields import ChoiceField, FloatField, IntegerField
from datelier.gui.components.groups import Conditional
from datelier.plotting.categories import CategoryRepresentation


class RelationshipSettings(Container):
    def __init__(self, plots: PlotState, choose_chart: Callable[[str], None]) -> None:
        def axis(attr: str, label: str) -> ColumnPicker:
            def selected() -> tuple[str, ...]:
                index = getattr(plots, attr)
                return (plots.numeric[index],) if plots.numeric else ()

            def choose(names: tuple[str, ...]) -> None:
                if names:
                    plots.choose_axis(attr, plots.numeric.index(names[0]))
                    plots.custom_scatter = True

            return ColumnPicker(
                attr,
                label,
                lambda: tuple(ColumnChoice(n, "Numeric", True) for n in plots.numeric),
                selected,
                choose,
                SingleSelection(),
            )

        def category(
            attr: str, label: str, choices: Callable[[], tuple[str, ...]]
        ) -> ColumnPicker:
            return ColumnPicker(
                attr,
                label,
                lambda: tuple(ColumnChoice(n) for n in choices()),
                lambda: (name,) if (name := getattr(plots, attr)) else (),
                lambda names: (
                    plots.choose_category(names[0])
                    if attr == "category_column" and names
                    else setattr(plots, attr, next(iter(names), None))
                ),
                SingleSelection(),
            )

        super().__init__(
            "relationships",
            (
                ChoiceField(
                    "chart",
                    "Chart",
                    lambda: plots.chart_choices,
                    lambda: plots.chart_choice,
                    choose_chart,
                ),
                Conditional(
                    "scatter",
                    lambda: plots.relationship_chart == "Scatter",
                    (
                        axis("x_index", "X coordinate"),
                        axis("y_index", "Y coordinate"),
                        ChoiceField(
                            "colors",
                            "Colors",
                            ("Uniform", "Column"),
                            lambda: plots.color_source,
                            plots.choose_color,
                        ),
                        ColumnPicker(
                            "color-column",
                            "Color column",
                            lambda: tuple(ColumnChoice(n) for n in plots.color_columns),
                            lambda: (plots.color_column,) if plots.color_column else (),
                            lambda names: setattr(
                                plots,
                                "color_index",
                                plots.color_columns.index(names[0]) + 1 if names else 0,
                            ),
                            SingleSelection(),
                        ),
                    ),
                ),
                Conditional(
                    "categories",
                    lambda: plots.relationship_chart != "Scatter",
                    (
                        category(
                            "category_column", "Category", lambda: plots.categories
                        ),
                        Conditional(
                            "grouped",
                            lambda: (
                                plots.relationship_chart
                                == CategoryRepresentation.GROUPED
                            ),
                            (
                                category(
                                    "category_group",
                                    "Group by",
                                    lambda: tuple(
                                        n
                                        for n in plots.categories
                                        if n != plots.category_column
                                    ),
                                ),
                            ),
                        ),
                        Conditional(
                            "numeric-value",
                            lambda: (
                                plots.relationship_chart
                                not in (
                                    CategoryRepresentation.COUNTS,
                                    CategoryRepresentation.GROUPED,
                                )
                            ),
                            (
                                category(
                                    "category_value",
                                    "Numeric value",
                                    lambda: plots.numeric,
                                ),
                            ),
                        ),
                        IntegerField(
                            "top",
                            "Visible categories",
                            lambda: plots.top_counts,
                            lambda v: setattr(plots, "top_counts", v),
                            1,
                            30,
                        ),
                        Conditional(
                            "violin",
                            lambda: (
                                plots.relationship_chart
                                == CategoryRepresentation.VIOLIN
                            ),
                            (
                                FloatField(
                                    "bandwidth",
                                    "Density bandwidth",
                                    lambda: plots.bandwidth,
                                    lambda v: setattr(plots, "bandwidth", v),
                                    0.05,
                                    4,
                                ),
                                IntegerField(
                                    "seed",
                                    "Density seed",
                                    lambda: plots.seed,
                                    lambda v: setattr(plots, "seed", v),
                                    0,
                                    2**32 - 1,
                                ),
                            ),
                        ),
                    ),
                ),
                JobFeedback("plot-error", lambda: JobSnapshot(plots.error)),
                IntegerField(
                    "points",
                    "Displayed points",
                    lambda: plots.point_limit,
                    lambda value: setattr(plots, "point_limit", value),
                    1,
                    10000,
                ),
            ),
        )


class CorrelationSettings(Container):
    def __init__(self, plots: PlotState) -> None:
        super().__init__(
            "correlations",
            (
                ColumnPicker(
                    "features",
                    "Correlation features (up to 16)",
                    lambda: tuple(
                        ColumnChoice(n, "Numeric", True) for n in plots.numeric
                    ),
                    lambda: tuple(plots.relationship_features or ()),
                    lambda names: setattr(plots, "relationship_features", list(names)),
                    MultiSelection(limit=16),
                ),
            ),
        )
