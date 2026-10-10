"""Algorithm-specific editor families built from shared typed field components."""

from abc import ABC
from collections.abc import Callable, Mapping
from dataclasses import fields
from typing import cast

from datelier.analysis.parameters import ExtraParameters
from datelier.analysis.types import LIMITS, Algorithm
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


def real(
    model: AnalysisSettings,
    name: str,
    label: str,
    minimum: float = 0,
    maximum: float = 100000,
) -> FloatField:
    return FloatField(
        name,
        label,
        lambda: cast(float, getattr(model, name)),
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


def choice(
    model: AnalysisSettings, name: str, label: str, labels: tuple[str, ...]
) -> ChoiceField[int]:
    return ChoiceField(
        name,
        label,
        tuple(range(len(labels))),
        lambda: cast(int, getattr(model, name)),
        lambda value: setattr(model, name, value),
        labels,
    )


def parameter_field(
    name: str,
    label: str,
    value: object,
    get: Callable[[], object],
    set_value: Callable[[object], None],
    metadata: Mapping[str, object],
) -> Component:
    minimum = cast(float, metadata.get("min", 0))
    maximum = cast(float, metadata.get("max", 1000000))
    makers: dict[type, Callable[[], Component]] = {
        bool: lambda: BooleanField(name, label, lambda: cast(bool, get()), set_value),
        int: lambda: IntegerField(
            name, label, lambda: cast(int, get()), set_value, int(minimum), int(maximum)
        ),
        float: lambda: FloatField(
            name,
            label,
            lambda: cast(float, get()),
            set_value,
            float(minimum),
            float(maximum),
        ),
        str: lambda: ChoiceField(
            name,
            label,
            cast(tuple[str, ...], metadata["choices"]),
            lambda: cast(str, get()),
            set_value,
        ),
    }
    return makers[type(value)]()


class AlgorithmSettings(Container, ABC):
    """Each concrete method owns its parameter fields and limits."""


class PCASettings(AlgorithmSettings):
    def __init__(self, model: AnalysisSettings) -> None:
        super().__init__(
            "PCA",
            (
                integer(model, "pca_limit", "Rows (max 100k)"),
                choice(model, "pca_solver", "Solver", ("randomized", "full")),
                boolean(model, "pca_whiten", "Whitening"),
            ),
        )


class KMeansSettings(AlgorithmSettings):
    def __init__(self, model: AnalysisSettings) -> None:
        super().__init__(
            "k-means",
            (
                integer(model, "kmeans_limit", "Rows (max 100k)"),
                integer(model, "clusters", "Clusters", maximum=256),
                integer(model, "initializations", "Initializations"),
                integer(model, "kmeans_iterations", "Iterations"),
            ),
        )


class TSNESettings(AlgorithmSettings):
    def __init__(self, model: AnalysisSettings) -> None:
        super().__init__(
            "t-SNE",
            (
                integer(model, "tsne_limit", "Rows (max 10k)", maximum=10000),
                real(model, "perplexity", "Perplexity", minimum=0.1),
                integer(model, "tsne_iterations", "Iterations", minimum=250),
                boolean(model, "tsne_auto_rate", "Automatic learning rate"),
                real(model, "tsne_rate", "Learning rate", minimum=0.1),
                choice(model, "tsne_init", "Initialization", ("pca", "random")),
            ),
        )


class UMAPSettings(AlgorithmSettings):
    def __init__(self, model: AnalysisSettings) -> None:
        super().__init__(
            "UMAP",
            (
                integer(model, "umap_limit", "Rows (max 50k)", maximum=50000),
                integer(model, "neighbors", "Neighbors", minimum=2),
                real(model, "min_distance", "Minimum distance", maximum=1),
                choice(model, "umap_metric", "Metric", ("euclidean", "cosine")),
            ),
        )


class ExtraSettings(AlgorithmSettings):
    def __init__(self, model: AnalysisSettings, algorithm: Algorithm) -> None:
        self.model, self.algorithm = model, algorithm
        self.conditions: dict[str, Callable[[], bool]] = {}
        children: list[Component] = [
            IntegerField(
                "limit",
                f"Rows (max {LIMITS[algorithm]:,})",
                lambda: model.extra_limits[algorithm],
                lambda value: model.extra_limits.__setitem__(algorithm, value),
                1,
                LIMITS[algorithm],
            )
        ]
        parameters = model.extra_parameters[algorithm]
        for item in fields(parameters):
            name = item.name
            label = str(item.metadata["label"])
            value: object = getattr(parameters, name)

            def get(name: str = name) -> object:
                return getattr(model.extra_parameters[algorithm], name)

            def set_value(new: object, name: str = name) -> None:
                self.update(name, new)

            children.append(
                parameter_field(name, label, value, get, set_value, item.metadata)
            )
            if "when" in item.metadata:
                dependency, active = item.metadata["when"]
                self.conditions[name] = lambda dependency=dependency, active=active: (
                    getattr(model.extra_parameters[algorithm], dependency) == active
                )
            if "unless" in item.metadata:
                dependency, inactive = item.metadata["unless"]
                self.conditions[name] = (
                    lambda dependency=dependency, inactive=inactive: (
                        getattr(model.extra_parameters[algorithm], dependency)
                        not in inactive
                    )
                )
        super().__init__(algorithm.value, tuple(children))

    def update(self, name: str, value: object) -> None:
        parameters = self.model.extra_parameters[self.algorithm]
        values = {
            item.name: getattr(parameters, item.name) for item in fields(parameters)
        }
        values[name] = value
        constructor = cast(Callable[..., ExtraParameters], type(parameters))
        self.model.extra_parameters[self.algorithm] = constructor(**values)

    def render(self, frame: FrameContext) -> None:
        for child in self.children:
            visible = self.conditions.get(child.key)
            if visible is None or visible():
                child.render(frame.child(child.key))


class AlgorithmEditors(Container):
    def __init__(
        self, model: AnalysisSettings, selected: Callable[[], Algorithm]
    ) -> None:
        self.selected = selected
        self.registry: dict[Algorithm, AlgorithmSettings] = {
            algorithm: ExtraSettings(model, algorithm)
            for algorithm in model.extra_parameters
        }
        self.registry.update(
            {
                Algorithm.PCA: PCASettings(model),
                Algorithm.KMEANS: KMeansSettings(model),
                Algorithm.TSNE: TSNESettings(model),
                Algorithm.UMAP: UMAPSettings(model),
            }
        )
        super().__init__("parameters", ())

    def render(self, frame: FrameContext) -> None:
        self.children = (self.registry[self.selected()],)
        super().render(frame)
