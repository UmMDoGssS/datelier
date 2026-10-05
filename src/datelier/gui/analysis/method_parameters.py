"""Compact parameter forms from the trusted, typed method records."""

from collections.abc import Callable
from dataclasses import fields
from typing import TYPE_CHECKING, cast

from imgui_bundle import imgui

from datelier.analysis.algorithm import Algorithm
from datelier.analysis.parameters import EXTRA_LIMITS, ExtraParameters
from datelier.gui.widgets.fields import combo, field

if TYPE_CHECKING:
    from datelier.gui.analysis.controls import AnalysisControls


def show_extra_parameters(controls: AnalysisControls, algorithm: Algorithm) -> None:
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
        if isinstance(value, bool):
            changed, new = imgui.checkbox(label, value)
        elif isinstance(value, int):
            changed, new = imgui.input_int(field(label), value)
        elif isinstance(value, float):
            changed, new = imgui.input_double(field(label), value, format="%.6g")
        elif isinstance(value, str):
            choices = list(cast(tuple[str, ...], item.metadata["choices"]))
            changed, index = combo(label, choices.index(value), choices)
            new = choices[index]
        else:
            raise TypeError("Unsupported analysis parameter field")
        if changed:
            updates[item.name] = new
    if updates:
        # Typed dataclasses are trusted; reflection is confined to this form.
        values = {
            item.name: getattr(parameters, item.name) for item in fields(parameters)
        }
        constructor = cast(Callable[..., ExtraParameters], type(parameters))
        controls.extra_parameters[algorithm] = constructor(**(values | updates))
