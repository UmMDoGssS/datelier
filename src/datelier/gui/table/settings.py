"""Display-only table settings reuse the shared typed controls."""

from dataclasses import replace

from datelier.application.tabular import PresentationController
from datelier.gui.components.actions import CommandButton
from datelier.gui.components.inputs import BooleanField, ChoiceField, FloatField
from datelier.gui.components.layout import Container
from datelier.gui.components.layout.groups import Conditional
from datelier.inspection.presentation import NumericScale


class PresentationSettings(Container):
    def __init__(self, model: PresentationController) -> None:
        super().__init__(
            "presentation",
            (
                BooleanField(
                    "colors",
                    "Conditional cell colors",
                    lambda: model.settings.enabled,
                    lambda v: setattr(
                        model, "settings", replace(model.settings, enabled=v)
                    ),
                ),
                BooleanField(
                    "badges",
                    "Interpretation badges",
                    lambda: model.settings.badges,
                    lambda v: setattr(
                        model, "settings", replace(model.settings, badges=v)
                    ),
                ),
                ChoiceField(
                    "scale",
                    "Numeric scale",
                    tuple(NumericScale),
                    lambda: model.settings.scale,
                    lambda v: setattr(
                        model, "settings", replace(model.settings, scale=v)
                    ),
                ),
                Conditional(
                    "custom",
                    lambda: model.settings.scale == NumericScale.CUSTOM,
                    (
                        FloatField(
                            "minimum",
                            "Shading minimum",
                            lambda: model.minimum,
                            lambda v: setattr(model, "minimum", v),
                            -1e300,
                            1e300,
                        ),
                        FloatField(
                            "maximum",
                            "Shading maximum",
                            lambda: model.maximum,
                            lambda v: setattr(model, "maximum", v),
                            -1e300,
                            1e300,
                        ),
                        CommandButton("apply", "Apply shading range", model.apply),
                    ),
                ),
            ),
        )
