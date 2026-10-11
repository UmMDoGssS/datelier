"""Shared, validated density preparation controls for Profiles and Relationships."""

from datelier.application.plot_settings import PlotState
from datelier.gui.components.base import Container
from datelier.gui.components.fields import FloatField, IntegerField


class DistributionTuning(Container):
    def __init__(self, plots: PlotState) -> None:
        super().__init__(
            "density-tuning",
            (
                FloatField(
                    "bandwidth",
                    "Density bandwidth",
                    lambda: plots.bandwidth,
                    lambda v: setattr(plots, "bandwidth", v),
                    0.1,
                    5,
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
        )
