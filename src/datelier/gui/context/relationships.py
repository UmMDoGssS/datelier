"""Coordinate, color and correlation drafts use independent column pickers."""

from collections.abc import Callable

from datelier.analysis.types import Algorithm, EmbeddingResult
from datelier.application.analysis import AnalysisController
from datelier.application.columns import ColumnChoice, MultiSelection, SingleSelection
from datelier.application.plot_settings import PlotState
from datelier.gui.components.actions import JobFeedback, JobSnapshot
from datelier.gui.components.base import Container
from datelier.gui.components.columns import ColumnPicker
from datelier.gui.components.fields import ChoiceField, FloatField, IntegerField
from datelier.gui.components.groups import Conditional
from datelier.gui.profiles.series import SERIES_TYPES
from datelier.plotting.categories import CategoryRepresentation


class RelationshipSettings(Container):
    def __init__(
        self,
        plots: PlotState,
        choose_chart: Callable[[str], None],
        analysis: AnalysisController,
    ) -> None:
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
                        ChoiceField(
                            "coordinates",
                            "Coordinates",
                            (None, *(a for a in Algorithm if not a.is_clustering)),
                            lambda: analysis.source,
                            analysis.choose_source,
                            labels=lambda: tuple(
                                [
                                    "Raw columns",
                                    *(
                                        f"{a.value} ({r.values.shape[1]}D)"
                                        if isinstance(
                                            r := analysis.jobs.results.get(a),
                                            EmbeddingResult,
                                        )
                                        and analysis.dataset is not None
                                        and r.revision == analysis.dataset.revision
                                        else f"{a.value} (prepare explicitly)"
                                        for a in Algorithm
                                        if not a.is_clustering
                                    ),
                                ]
                            ),
                        ),
                        Conditional(
                            "raw-coordinates",
                            lambda: analysis.source is None,
                            (
                                axis("x_index", "X coordinate"),
                                axis("y_index", "Y coordinate"),
                                Conditional(
                                    "z",
                                    lambda: plots.three_d,
                                    (axis("z_index", "Z coordinate"),),
                                ),
                            ),
                        ),
                        ChoiceField(
                            "colors",
                            "Colors",
                            (
                                "Uniform",
                                "Column",
                                *(a.value for a in Algorithm if a.is_clustering),
                            ),
                            lambda: plots.color_source,
                            plots.choose_color,
                        ),
                        Conditional(
                            "column-colors",
                            lambda: plots.color_source == "Column",
                            (
                                ColumnPicker(
                                    "color-column",
                                    "Color column",
                                    lambda: tuple(
                                        ColumnChoice(n) for n in plots.color_columns
                                    ),
                                    lambda: (
                                        (plots.color_column,)
                                        if plots.color_column
                                        else ()
                                    ),
                                    lambda names: setattr(
                                        plots,
                                        "color_index",
                                        plots.color_columns.index(names[0]) + 1
                                        if names
                                        else 0,
                                    ),
                                    SingleSelection(),
                                ),
                            ),
                        ),
                        JobFeedback(
                            "color-feedback",
                            lambda: JobSnapshot(
                                f"{plots.color_source}: no current fitted colors. "
                                "run the analysis explicitly."
                                if plots.cluster_color and plots.cluster_result is None
                                else ""
                            ),
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
    def __init__(
        self,
        plots: PlotState,
        read_mode: Callable[[], int],
        write_mode: Callable[[int], None],
    ) -> None:
        super().__init__(
            "correlations",
            (
                ChoiceField(
                    "mode",
                    "View",
                    (0, 1),
                    read_mode,
                    write_mode,
                    labels=("Heatmap", "Pair grid"),
                ),
                Conditional(
                    "diagonal",
                    lambda: read_mode() == 1,
                    (
                        ChoiceField(
                            "mode",
                            "Diagonal",
                            tuple(range(5)),
                            lambda: plots.diagonal_mode,
                            lambda v: setattr(plots, "diagonal_mode", v),
                            labels=tuple(s.label for s in SERIES_TYPES),
                        ),
                        Conditional(
                            "curves",
                            lambda: plots.diagonal_mode in (1, 4),
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
                                    "Curve seed",
                                    lambda: plots.seed,
                                    lambda v: setattr(plots, "seed", v),
                                    0,
                                    2**32 - 1,
                                ),
                            ),
                        ),
                    ),
                ),
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
