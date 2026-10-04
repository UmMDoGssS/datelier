"""Completed-analysis plot switching and background preparation integration."""

from dataclasses import dataclass, field

from imgui_bundle import hello_imgui, imgui

from datelier.analysis_jobs import AnalysisJobs
from datelier.analysis_plots import AnalysisPlots
from datelier.analysis_types import Algorithm, EmbeddingResult
from datelier.dataset import Dataset
from datelier.gui_analysis_controls import AnalysisControls
from datelier.gui_analysis_form import show_inputs, show_parameters
from datelier.gui_fields import combo
from datelier.gui_plot_controls import PlotControls
from datelier.plotting import Scatter


@dataclass
class AnalysisSession:
    controls: AnalysisControls = field(default_factory=AnalysisControls)
    jobs: AnalysisJobs = field(default_factory=AnalysisJobs)
    plots: AnalysisPlots = field(default_factory=AnalysisPlots)
    source: Algorithm | None = None
    inputs_pixel: tuple[float, float] = (0, 0)
    coordinates_pixel: tuple[float, float] = (0, 0)
    run_pixel: tuple[float, float] = (0, 0)

    def poll(self, dataset: Dataset | None) -> bool:
        revision = dataset.revision if dataset is not None else None
        completed = self.jobs.poll(revision)
        if completed:
            latest = self.jobs.latest
            if isinstance(latest, EmbeddingResult):
                self.source = latest.provenance.request.algorithm
        self.plots.poll(revision)
        return completed and isinstance(self.jobs.latest, EmbeddingResult)

    def scatter_controls(self, dataset: Dataset, plots: PlotControls) -> Scatter | None:
        algorithms = [Algorithm.PCA, Algorithm.TSNE, Algorithm.UMAP]
        index = algorithms.index(self.source) + 1 if self.source in algorithms else 0
        changed, index = combo("Coordinates", index, ["Columns", *map(str, algorithms)])
        pos, size = imgui.get_item_rect_min(), imgui.get_item_rect_size()
        self.coordinates_pixel = (pos.x + size.x / 2, pos.y + size.y / 2)
        if changed:
            self.source = algorithms[index - 1] if index else None
        if self.source is None:
            return None
        plots.show_color()
        result = self.jobs.results.get(self.source)
        state = "setup" if result is None else "fitted"
        if imgui.collapsing_header(
            f"Inputs and settings##{self.source}-{state}",
            flags=imgui.TreeNodeFlags_.default_open if result is None else 0,
        ):
            imgui.begin_disabled(self.jobs.busy)
            show_inputs(self.controls)
            if imgui.tree_node(f"{self.source} parameters"):
                show_parameters(self.controls, self.source)
                imgui.tree_pop()
            imgui.end_disabled()
            open_inputs = imgui.button("Open Analysis panel")
            pos, size = imgui.get_item_rect_min(), imgui.get_item_rect_size()
            self.inputs_pixel = (pos.x + size.x / 2, pos.y + size.y / 2)
            if open_inputs:
                hello_imgui.get_runner_params().docking_params.focus_dockable_window(
                    "Analysis"
                )
        imgui.begin_disabled(self.jobs.busy or not self.controls.features)
        if imgui.button(f"Run {self.source}"):
            self.controls.start(self.jobs, dataset, self.source)
        pos, size = imgui.get_item_rect_min(), imgui.get_item_rect_size()
        self.run_pixel = (pos.x + size.x / 2, pos.y + size.y / 2)
        imgui.end_disabled()
        if self.controls.error:
            imgui.text_wrapped(self.controls.error)
        if self.jobs.busy:
            imgui.same_line()
            if imgui.button("Cancel"):
                self.jobs.cancel()
            imgui.text_wrapped(f"{self.jobs.phase} · {self.jobs.elapsed:.1f}s")
        elif self.jobs.message.startswith(("Analysis failed", "Analysis cancelled")):
            imgui.text_wrapped(self.jobs.message)
        if not isinstance(result, EmbeddingResult):
            return None
        if self.controls.request(self.source) != result.provenance.request:
            imgui.text_wrapped(
                f"Inputs changed; run {self.source} to update this result."
            )
        color = (
            plots.color_columns[plots.color_index - 1] if plots.color_index else None
        )
        self.plots.ensure(
            dataset,
            result,
            plots.point_limit,
            color,
            plots.cluster_result if plots.cluster_color else None,
        )
        if self.plots.active is None:
            imgui.text_wrapped(self.plots.message)
        summary = result.provenance.input
        imgui.text_wrapped(
            f"{summary.sampled_rows:,} fitted / {summary.eligible_rows:,} eligible · "
            f"{summary.excluded_rows:,} excluded"
        )
        return self.plots.active

    def close(self) -> None:
        self.jobs.close()
        self.plots.close()
