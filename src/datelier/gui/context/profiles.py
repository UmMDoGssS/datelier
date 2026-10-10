"""Profile settings compose shared selectors and typed fields."""

from datelier.application.plot_settings import PlotState
from datelier.application.profiles import ProfileController
from datelier.gui.components.base import Container
from datelier.gui.components.columns import ColumnPicker
from datelier.gui.components.fields import BooleanField, ChoiceField, IntegerField
from datelier.gui.profiles.charts import CHARTS


class ProfileSettings(Container):
    def __init__(self, profiles: ProfileController, plots: PlotState) -> None:
        super().__init__(
            "profiles",
            (
                ColumnPicker(
                    "columns",
                    "Profile columns",
                    lambda: profiles.choices,
                    lambda: profiles.selected,
                    profiles.choose,
                    profiles.policy,
                ),
                ChoiceField(
                    "representation",
                    "Representation",
                    tuple(range(5)),
                    lambda: profiles.mode,
                    lambda value: setattr(profiles, "mode", value),
                    tuple(chart.label for chart in CHARTS),
                ),
                IntegerField(
                    "bins",
                    "Histogram bins",
                    lambda: plots.bins,
                    lambda value: setattr(plots, "bins", value),
                    1,
                    100,
                ),
                BooleanField(
                    "standardize",
                    "Standardize",
                    lambda: plots.standardize,
                    lambda value: setattr(plots, "standardize", value),
                ),
                BooleanField(
                    "density",
                    "Histogram density",
                    lambda: plots.density,
                    lambda value: setattr(plots, "density", value),
                ),
            ),
        )
