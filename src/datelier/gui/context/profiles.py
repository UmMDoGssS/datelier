"""Profile settings compose shared selectors and typed fields."""

from datelier.application.plot_settings import PlotState
from datelier.application.profiles import ProfileController, ProfileFamily
from datelier.gui.components.base import Container
from datelier.gui.components.columns import ColumnPicker
from datelier.gui.components.fields import BooleanField, ChoiceField, IntegerField
from datelier.gui.components.groups import Conditional
from datelier.gui.context.distributions import DistributionTuning
from datelier.gui.profiles.series import SERIES_TYPES


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
                Conditional(
                    "text-tools",
                    lambda: profiles.text_optional,
                    (
                        BooleanField(
                            "text",
                            "Text tools",
                            lambda: profiles.text,
                            lambda value: setattr(profiles, "text", value),
                        ),
                    ),
                ),
                Conditional(
                    "numeric-controls",
                    lambda: (
                        profiles.family == ProfileFamily.COLUMNS and profiles.numeric
                    ),
                    (
                        ChoiceField(
                            "representation",
                            "Representation",
                            tuple(range(5)),
                            lambda: profiles.mode,
                            lambda value: setattr(profiles, "mode", value),
                            tuple(chart.label for chart in SERIES_TYPES),
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
                        Conditional(
                            "curves",
                            lambda: profiles.mode in (1, 4),
                            (DistributionTuning(plots),),
                        ),
                    ),
                ),
                Conditional(
                    "count-controls",
                    lambda: (
                        profiles.family == ProfileFamily.COLUMNS and profiles.countable
                    ),
                    (
                        IntegerField(
                            "top",
                            "Visible values",
                            lambda: plots.top_counts,
                            lambda v: setattr(plots, "top_counts", v),
                            1,
                            100,
                        ),
                    ),
                ),
            ),
        )
