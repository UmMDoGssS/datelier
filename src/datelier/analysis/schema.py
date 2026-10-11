"""Trusted parameter descriptors shared by validation and GUI rendering."""

import math
from dataclasses import dataclass, fields, is_dataclass
from enum import StrEnum
from typing import cast

type ParameterValue = bool | int | float | str


class ParameterKind(StrEnum):
    BOOLEAN = "boolean"
    INTEGER = "integer"
    REAL = "real"
    CHOICE = "choice"


@dataclass(frozen=True)
class Parameter:
    name: str
    label: str
    kind: ParameterKind
    default: ParameterValue
    minimum: float = 0
    maximum: float = 1e6
    choices: tuple[str, ...] = ()
    when: tuple[str, ParameterValue] | None = None
    unless: tuple[str, tuple[str, ...]] | None = None
    automatic: str | None = None
    manual_default: float = 1

    def visible(self, parameters: object) -> bool:
        if self.when is not None:
            name, active = self.when
            if getattr(parameters, name) != active:
                return False
        if self.unless is not None:
            name, inactive = self.unless
            if getattr(parameters, name) in inactive:
                return False
        return True

    def validate(self, value: object) -> None:
        if self.automatic is not None and value == self.automatic:
            return
        if self.kind == ParameterKind.BOOLEAN:
            valid = type(value) is bool
        elif self.kind == ParameterKind.CHOICE:
            valid = type(value) is str and value in self.choices
        else:
            valid = (
                type(value) is int
                if self.kind == ParameterKind.INTEGER
                else type(value) in (int, float)
            )
            valid = (
                valid
                and isinstance(value, (int, float))
                and math.isfinite(value)
                and self.minimum <= value <= self.maximum
            )
        if not valid:
            raise ValueError(f"{self.label} is outside its supported choices or bounds")


def parameter_schema(parameters: object) -> tuple[Parameter, ...]:
    if not is_dataclass(parameters) or isinstance(parameters, type):
        raise TypeError("Algorithm settings must be a trusted dataclass instance")
    kinds: dict[type, ParameterKind] = {
        bool: ParameterKind.BOOLEAN,
        int: ParameterKind.INTEGER,
        float: ParameterKind.REAL,
        str: ParameterKind.CHOICE,
    }
    return tuple(
        Parameter(
            item.name,
            str(item.metadata["label"]),
            ParameterKind(item.metadata["kind"])
            if "kind" in item.metadata
            else kinds[type(item.default)],
            cast(ParameterValue, item.default),
            float(item.metadata.get("min", 0)),
            float(item.metadata.get("max", 1e6)),
            cast(tuple[str, ...], item.metadata.get("choices", ())),
            cast(tuple[str, ParameterValue] | None, item.metadata.get("when")),
            cast(tuple[str, tuple[str, ...]] | None, item.metadata.get("unless")),
            cast(str | None, item.metadata.get("automatic")),
            float(item.metadata.get("manual_default", 1)),
        )
        for item in fields(parameters)
    )


def validate_parameters(parameters: object) -> None:
    for descriptor in parameter_schema(parameters):
        if descriptor.visible(parameters):
            descriptor.validate(getattr(parameters, descriptor.name))
