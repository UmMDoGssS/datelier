"""Analysis input and algorithm editor families with injected drafts."""

from abc import ABC
from dataclasses import dataclass

from imgui_bundle import imgui

from datelier.analysis.types import Algorithm
from datelier.application.analysis_settings import AnalysisSettings
from datelier.application.columns import ColumnChoice, MultiSelection
from datelier.gui.analysis.method_parameters import show_extra_parameters
from datelier.gui.components.base import BoundView, FrameContext
from datelier.gui.components.columns import ColumnPicker
from datelier.gui.components.probe import GuiProbe, ViewScope
from datelier.gui.widgets.fields import combo, field


@dataclass(frozen=True)
class AnalysisInputBinding:
    settings: AnalysisSettings
    dimensions: bool = True
    fixed_dimensions: int | None = None


class AnalysisInputs(BoundView[AnalysisInputBinding]):
    def __init__(self) -> None:
        self.picker = ColumnPicker("Analysis features", MultiSelection(limit=128))

    def show(
        self,
        controls: AnalysisSettings,
        *,
        dimensions: bool = True,
        fixed_dimensions: int | None = None,
    ) -> None:
        self.bind_view(AnalysisInputBinding(controls, dimensions, fixed_dimensions))
        self.render(FrameContext(ViewScope(""), GuiProbe()))

    def draw(self, binding: AnalysisInputBinding, frame: FrameContext) -> None:
        controls, dimensions, fixed_dimensions = (
            binding.settings,
            binding.dimensions,
            binding.fixed_dimensions,
        )
        controls.features = list(
            self.picker.show(
                tuple(
                    ColumnChoice(n, "Numeric", numeric=True) for n in controls.numeric
                ),
                tuple(controls.features),
                caption=f"Features ({len(controls.features)})",
                frame=frame,
            )
        )
        if controls.features:
            imgui.text_wrapped(", ".join(controls.features))
        else:
            imgui.text("Choose features before running analysis.")
        _, controls.standardize = imgui.checkbox(
            "Standardize features", controls.standardize
        )
        _, controls.impute = imgui.checkbox(
            "Fill missing values with median", controls.impute
        )
        editable_dimensions = dimensions and fixed_dimensions is None
        if fixed_dimensions is not None:
            imgui.text(f"Components: {fixed_dimensions}")
        if imgui.begin_table(
            "Analysis dimensions and seed", 2 if editable_dimensions else 1
        ):
            imgui.table_next_row()
            imgui.table_set_column_index(0)
            if editable_dimensions:
                changed, dims = combo(
                    "Output dimensions", controls.dimensions - 2, ["2", "3"]
                )
                if changed:
                    controls.dimensions = dims + 2
                imgui.table_set_column_index(1)
            _, controls.seed = imgui.input_int(field("Random seed"), controls.seed)
            imgui.end_table()


@dataclass(frozen=True)
class AlgorithmParameterBinding:
    settings: AnalysisSettings
    algorithm: Algorithm


class AlgorithmParameterEditor(BoundView[AlgorithmParameterBinding], ABC):
    pass


class PCAParameterEditor(AlgorithmParameterEditor):
    def draw(self, binding: AlgorithmParameterBinding, frame: FrameContext) -> None:
        controls = binding.settings
        _, controls.pca_limit = imgui.input_int(
            field("Rows (max 100k)"), controls.pca_limit
        )
        _, controls.pca_solver = combo(
            "Solver", controls.pca_solver, ["randomized", "full"]
        )
        _, controls.pca_whiten = imgui.checkbox("Whitening", controls.pca_whiten)


class TSNEParameterEditor(AlgorithmParameterEditor):
    def draw(self, binding: AlgorithmParameterBinding, frame: FrameContext) -> None:
        controls = binding.settings
        _, controls.tsne_limit = imgui.input_int(
            field("Rows (max 10k)"), controls.tsne_limit
        )
        _, controls.perplexity = imgui.input_float(
            field("Perplexity"), controls.perplexity
        )
        _, controls.tsne_iterations = imgui.input_int(
            field("Iterations"), controls.tsne_iterations
        )
        _, controls.tsne_auto_rate = imgui.checkbox(
            "Automatic learning rate", controls.tsne_auto_rate
        )
        if not controls.tsne_auto_rate:
            _, controls.tsne_rate = imgui.input_float(
                field("Learning rate"), controls.tsne_rate
            )
        _, controls.tsne_init = combo(
            "Initialization", controls.tsne_init, ["pca", "random"]
        )


class UMAPParameterEditor(AlgorithmParameterEditor):
    def draw(self, binding: AlgorithmParameterBinding, frame: FrameContext) -> None:
        controls = binding.settings
        _, controls.umap_limit = imgui.input_int(
            field("Rows (max 50k)"), controls.umap_limit
        )
        _, controls.neighbors = imgui.input_int(field("Neighbors"), controls.neighbors)
        _, controls.min_distance = imgui.slider_float(
            field("Minimum distance"), controls.min_distance, 0, 1
        )
        _, controls.umap_metric = combo(
            "Metric", controls.umap_metric, ["euclidean", "cosine"]
        )


class KMeansParameterEditor(AlgorithmParameterEditor):
    def draw(self, binding: AlgorithmParameterBinding, frame: FrameContext) -> None:
        controls = binding.settings
        _, controls.kmeans_limit = imgui.input_int(
            field("Rows (max 100k)"), controls.kmeans_limit
        )
        _, controls.clusters = imgui.input_int(
            field("Clusters (max 256)"), controls.clusters
        )
        _, controls.initializations = imgui.input_int(
            field("Initializations"), controls.initializations
        )
        _, controls.kmeans_iterations = imgui.input_int(
            field("Iterations"), controls.kmeans_iterations
        )


class ExtraParameterEditor(AlgorithmParameterEditor):
    def draw(self, binding: AlgorithmParameterBinding, frame: FrameContext) -> None:
        show_extra_parameters(binding.settings, binding.algorithm)


class AlgorithmParameters(BoundView[AlgorithmParameterBinding]):
    def __init__(self) -> None:
        extra = ExtraParameterEditor()
        self.editors: dict[Algorithm, AlgorithmParameterEditor] = {
            a: extra for a in Algorithm
        }
        self.editors.update(
            {
                Algorithm.PCA: PCAParameterEditor(),
                Algorithm.TSNE: TSNEParameterEditor(),
                Algorithm.UMAP: UMAPParameterEditor(),
                Algorithm.KMEANS: KMeansParameterEditor(),
            }
        )

    def show(self, controls: AnalysisSettings, algorithm: Algorithm) -> None:
        self.bind_view(AlgorithmParameterBinding(controls, algorithm))
        self.render(FrameContext(ViewScope(""), GuiProbe()))

    def draw(self, binding: AlgorithmParameterBinding, frame: FrameContext) -> None:
        editor = self.editors[binding.algorithm]
        editor.bind_view(binding)
        editor.render(frame.child(str(binding.algorithm)))
