"""Trusted parameter types dispatch to a shared abstract field editor family."""

from abc import ABC, abstractmethod
from collections.abc import Mapping
from typing import cast

from imgui_bundle import imgui

from datelier.gui.widgets.fields import combo, field


class ParameterField(ABC):
    @abstractmethod
    def edit(
        self, label: str, value: object, metadata: Mapping[str, object]
    ) -> tuple[bool, object]: ...


class BooleanField(ParameterField):
    def edit(
        self, label: str, value: object, metadata: Mapping[str, object]
    ) -> tuple[bool, object]:
        return imgui.checkbox(label, cast(bool, value))


class IntegerField(ParameterField):
    def edit(
        self, label: str, value: object, metadata: Mapping[str, object]
    ) -> tuple[bool, object]:
        return imgui.input_int(field(label), cast(int, value))


class FloatField(ParameterField):
    def edit(
        self, label: str, value: object, metadata: Mapping[str, object]
    ) -> tuple[bool, object]:
        return imgui.input_double(field(label), cast(float, value), format="%.6g")


class ChoiceField(ParameterField):
    def edit(
        self, label: str, value: object, metadata: Mapping[str, object]
    ) -> tuple[bool, object]:
        choices = list(cast(tuple[str, ...], metadata["choices"]))
        changed, index = combo(label, choices.index(cast(str, value)), choices)
        return changed, choices[index]


FIELDS: dict[type, ParameterField] = {
    bool: BooleanField(),
    int: IntegerField(),
    float: FloatField(),
    str: ChoiceField(),
}
