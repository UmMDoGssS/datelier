"""Compact parameter forms from the trusted, typed method records."""

from collections.abc import Callable
from dataclasses import fields
from typing import TYPE_CHECKING, cast

from imgui_bundle import imgui

from datelier.analysis.algorithm import Algorithm
from datelier.analysis.parameters import EXTRA_LIMITS, ExtraParameters
from datelier.gui.analysis.parameter_fields import FIELDS
from datelier.gui.widgets.fields import field

if TYPE_CHECKING:
    from datelier.application.analysis_settings import AnalysisSettings


def show_extra_parameters(controls: AnalysisSettings, algorithm: Algorithm) -> None:
    _, controls.extra_limits[algorithm] = imgui.input_int(
        field(f"Rows (max {EXTRA_LIMITS[algorithm]:,})"),
        controls.extra_limits[algorithm],
    )
    parameters = controls.extra_parameters[algorithm]
    updates: dict[str, object] = {}
    for item in fields(parameters):
        if "when" in item.metadata:
            name, active = cast(tuple[str, object], item.metadata["when"])
            if getattr(parameters, name) != active:
                continue
        if "unless" in item.metadata:
            name, inactive = cast(tuple[str, tuple[str, ...]], item.metadata["unless"])
            if getattr(parameters, name) in inactive:
                continue
        value: object = getattr(parameters, item.name)
        label = str(item.metadata["label"])
        editor = FIELDS.get(type(value))
        if editor is None:
            raise TypeError("Unsupported analysis parameter field")
        changed, new = editor.edit(label, value, item.metadata)
        if changed:
            updates[item.name] = new
    if updates:
        # Typed dataclasses are trusted; reflection is confined to this form.
        values = {
            item.name: getattr(parameters, item.name) for item in fields(parameters)
        }
        constructor = cast(Callable[..., ExtraParameters], type(parameters))
        controls.extra_parameters[algorithm] = constructor(**(values | updates))
