"""Schema-driven analysis forms; algorithm knowledge belongs to the domain."""

from collections.abc import Callable
from typing import cast

from datelier.analysis.schema import Parameter, ParameterKind, ParameterValue
from datelier.analysis.types import Algorithm
from datelier.application.analysis_settings import AnalysisSettings
from datelier.gui.components.base import Component, Container, FrameContext
from datelier.gui.components.fields import (
    BooleanField,
    ChoiceField,
    FloatField,
    IntegerField,
)


def integer(
    model: AnalysisSettings,
    name: str,
    label: str,
    minimum: int = 1,
    maximum: int = 100000,
) -> IntegerField:
    return IntegerField(
        name,
        label,
        lambda: cast(int, getattr(model, name)),
        lambda value: setattr(model, name, value),
        minimum,
        maximum,
    )


def boolean(model: AnalysisSettings, name: str, label: str) -> BooleanField:
    return BooleanField(
        name,
        label,
        lambda: cast(bool, getattr(model, name)),
        lambda value: setattr(model, name, value),
    )


class AutomaticRealField(Container):
    """Preserve the last manual draft while toggling a schema-defined auto value."""

    def __init__(
        self,
        descriptor: Parameter,
        get: Callable[[], ParameterValue],
        set_value: Callable[[ParameterValue], None],
    ) -> None:
        self.descriptor, self.get, self.set_value = descriptor, get, set_value
        self.manual = descriptor.manual_default
        super().__init__(
            descriptor.name,
            (
                BooleanField(
                    "automatic",
                    "Automatic " + descriptor.label.lower(),
                    lambda: get() == descriptor.automatic,
                    self.toggle,
                ),
                FloatField(
                    "manual",
                    descriptor.label,
                    self.manual_value,
                    self.set_manual,
                    descriptor.minimum,
                    descriptor.maximum,
                ),
            ),
        )

    def manual_value(self) -> float:
        value = self.get()
        return float(value) if isinstance(value, (int, float)) else self.manual

    def set_manual(self, value: float) -> None:
        self.manual = value
        self.set_value(value)

    def toggle(self, automatic: bool) -> None:
        self.manual = self.manual_value()
        self.set_value(
            cast(str, self.descriptor.automatic) if automatic else self.manual
        )

    def render(self, frame: FrameContext) -> None:
        for child in self.children:
            if child.key == "automatic" or self.get() != self.descriptor.automatic:
                child.render(frame.child(child.key))


def parameter_field(
    descriptor: Parameter,
    get: Callable[[], ParameterValue],
    set_value: Callable[[ParameterValue], None],
) -> Component:
    name, label = descriptor.name, descriptor.label
    makers: dict[ParameterKind, Callable[[], Component]] = {
        ParameterKind.BOOLEAN: lambda: BooleanField(
            name, label, lambda: cast(bool, get()), set_value
        ),
        ParameterKind.INTEGER: lambda: IntegerField(
            name,
            label,
            lambda: cast(int, get()),
            set_value,
            int(descriptor.minimum),
            int(descriptor.maximum),
        ),
        ParameterKind.REAL: lambda: FloatField(
            name,
            label,
            lambda: float(get()),
            set_value,
            descriptor.minimum,
            descriptor.maximum,
        ),
        ParameterKind.CHOICE: lambda: ChoiceField(
            name, label, descriptor.choices, lambda: cast(str, get()), set_value
        ),
    }
    if descriptor.automatic is not None:
        return AutomaticRealField(descriptor, get, set_value)
    return makers[descriptor.kind]()


class AlgorithmSettings(Container):
    def __init__(self, model: AnalysisSettings, algorithm: Algorithm) -> None:
        self.model, self.algorithm = model, algorithm
        builder = model.parameters[algorithm]
        self.schema = builder.schema
        children: list[Component] = [
            IntegerField(
                "limit",
                f"Rows (max {builder.row_limit:,})",
                lambda: model.limits[algorithm],
                lambda value: model.limits.__setitem__(algorithm, value),
                1,
                builder.row_limit,
            )
        ]
        for descriptor in self.schema:
            name = descriptor.name

            def get(name: str = name) -> ParameterValue:
                return cast(ParameterValue, getattr(model.parameters[algorithm], name))

            def set_value(value: ParameterValue, name: str = name) -> None:
                model.update(algorithm, name, value)

            children.append(parameter_field(descriptor, get, set_value))
        super().__init__(algorithm.value, tuple(children))

    def render(self, frame: FrameContext) -> None:
        parameters = self.model.parameters[self.algorithm]
        visible = {item.name for item in self.schema if item.visible(parameters)}
        for child in self.children:
            if child.key == "limit" or child.key in visible:
                child.render(frame.child(child.key))


class AlgorithmEditors(Container):
    def __init__(
        self, model: AnalysisSettings, selected: Callable[[], Algorithm]
    ) -> None:
        self.selected = selected
        self.registry = {
            algorithm: AlgorithmSettings(model, algorithm)
            for algorithm in model.parameters
        }
        super().__init__("parameters", ())

    def render(self, frame: FrameContext) -> None:
        self.children = (self.registry[self.selected()],)
        super().render(frame)
