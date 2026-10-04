"""Shared, algorithm-specific analysis inputs for the panel and scatter view."""

from typing import TYPE_CHECKING

from imgui_bundle import imgui

from datelier.analysis_types import Algorithm
from datelier.gui_fields import combo, field

if TYPE_CHECKING:
    from datelier.gui_analysis_controls import AnalysisControls


def show_inputs(controls: AnalysisControls, *, dimensions: bool = True) -> None:
    if imgui.button(f"Features ({len(controls.features)})"):
        imgui.open_popup("Analysis features")
    if imgui.begin_popup("Analysis features"):
        if imgui.button("Select all"):
            controls.features = list(controls.numeric[:128])
        imgui.same_line()
        if imgui.button("Clear"):
            controls.features.clear()
        if imgui.begin_child("Feature list", (260, 140)):
            for name in controls.numeric:
                chosen = name in controls.features
                imgui.begin_disabled(not chosen and len(controls.features) >= 128)
                changed, checked = imgui.checkbox(name, chosen)
                imgui.end_disabled()
                if changed:
                    if checked:
                        controls.features.append(name)
                    else:
                        controls.features.remove(name)
        imgui.end_child()
        imgui.end_popup()
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
    if imgui.begin_table("Analysis dimensions and seed", 2 if dimensions else 1):
        imgui.table_next_row()
        imgui.table_set_column_index(0)
        if dimensions:
            changed, dims = combo(
                "Output dimensions", controls.dimensions - 2, ["2", "3"]
            )
            if changed:
                controls.dimensions = dims + 2
            imgui.table_set_column_index(1)
        _, controls.seed = imgui.input_int(field("Random seed"), controls.seed)
        imgui.end_table()


def show_parameters(controls: AnalysisControls, algorithm: Algorithm) -> None:
    if algorithm == Algorithm.PCA:
        _, controls.pca_limit = imgui.input_int(
            field("Rows (max 100k)"), controls.pca_limit
        )
        _, controls.pca_solver = combo(
            "Solver", controls.pca_solver, ["randomized", "full"]
        )
        _, controls.pca_whiten = imgui.checkbox("Whitening", controls.pca_whiten)
    elif algorithm == Algorithm.TSNE:
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
    elif algorithm == Algorithm.UMAP:
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
    else:
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
