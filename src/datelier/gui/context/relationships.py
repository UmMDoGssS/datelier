"""Coordinate, color and correlation drafts use independent column pickers."""

from datelier.application.columns import ColumnChoice, MultiSelection, SingleSelection
from datelier.application.plot_settings import PlotState
from datelier.gui.components.base import Container
from datelier.gui.components.columns import ColumnPicker
from datelier.gui.components.fields import ChoiceField, IntegerField


class RelationshipSettings(Container):
    def __init__(self, plots: PlotState) -> None:
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

        super().__init__(
            "relationships",
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
