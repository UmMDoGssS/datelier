"""Completed-analysis plot switching and background preparation integration."""

from dataclasses import dataclass, field

from imgui_bundle import hello_imgui, imgui

from datelier.analysis.jobs import AnalysisJobs
from datelier.analysis.plots import AnalysisPlots
from datelier.analysis.types import Algorithm, ClusteringResult, EmbeddingResult
from datelier.core.dataset import Dataset
from datelier.gui.analysis.controls import AnalysisControls
from datelier.gui.analysis.form import show_inputs, show_parameters
from datelier.gui.plots.controls import PlotControls
from datelier.gui.widgets.fields import combo
from datelier.inspection.exploration import Explorer
from datelier.plotting.data import Scatter


@dataclass
class AnalysisSession:
    controls: AnalysisControls = field(default_factory=AnalysisControls)
    jobs: AnalysisJobs = field(default_factory=AnalysisJobs)
    plots: AnalysisPlots = field(default_factory=AnalysisPlots)
    source: Algorithm | None = None
    panel_source: Algorithm | None = None
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
                self.panel_source = self.source
        self.plots.poll(revision)
        return completed and isinstance(self.jobs.latest, EmbeddingResult)

    def sync_dimensions(self, plots: PlotControls) -> None:
        self.controls.dimensions = plots.scatter_dimensions

    def show_panel(self, dataset: Dataset | None, plots: PlotControls) -> None:
        self.sync_dimensions(plots)
        self.controls.show(
            self.jobs,
            dataset,
            self.selected_algorithm(plots),
            fixed_dimensions=plots.scatter_dimensions,
        )

    def scatter_controls(
        self, dataset: Dataset, plots: PlotControls, explorer: Explorer
    ) -> Scatter | None:
        self.sync_dimensions(plots)
        algorithms = [a for a in Algorithm if not a.is_clustering]
        index = algorithms.index(self.source) + 1 if self.source in algorithms else 0
        if imgui.begin_table(
            "Scatter source", 2, imgui.TableFlags_.sizing_stretch_same
        ):
            imgui.table_next_row()
            imgui.table_set_column_index(0)
            changed, index = combo(
                "Coordinates", index, ["Columns", *map(str, algorithms)]
            )
            pos, size = imgui.get_item_rect_min(), imgui.get_item_rect_size()
            self.coordinates_pixel = (pos.x + size.x / 2, pos.y + size.y / 2)
            if changed:
                self.source = algorithms[index - 1] if index else None
                self.panel_source = self.source or plots.cluster_algorithm
            if self.source is None:
                plots.show_axes(explorer, dataset)
            imgui.table_set_column_index(1)
            if plots.show_color():
                self.panel_source = plots.cluster_algorithm or self.source
            imgui.end_table()
        cluster_algorithm = plots.cluster_algorithm
        if cluster_algorithm is not None:
            self.show_setup(dataset, cluster_algorithm, dimensions=False)
        if self.source is None:
            return None
        result = self.jobs.results.get(self.source)
        self.show_setup(dataset, self.source, dimensions=True)
        if not isinstance(result, EmbeddingResult):
            return None
        if result.values.shape[1] != plots.scatter_dimensions:
            imgui.text(f"Run {self.source} for {plots.chart_choice}.")
            return None
        color = plots.color_column
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

    def selected_algorithm(self, plots: PlotControls) -> Algorithm:
        return (
            self.panel_source
            or plots.cluster_algorithm
            or self.source
            or Algorithm.KMEANS
        )

    def sync_colors(self, plots: PlotControls) -> bool:
        algorithm = plots.cluster_algorithm
        result = self.jobs.results.get(algorithm) if algorithm is not None else None
        cluster = result if isinstance(result, ClusteringResult) else None
        if cluster is plots.cluster_result:
            return False
        plots.cluster_result = cluster
        plots.scatter_dirty = True
        return True

    def show_setup(
        self, dataset: Dataset, algorithm: Algorithm, *, dimensions: bool
    ) -> None:
        result = self.jobs.results.get(algorithm)
        state = "setup" if result is None else "fitted"
        imgui.push_id(str(algorithm))
        if imgui.collapsing_header(
            f"{algorithm} inputs and settings##{state}",
            flags=imgui.TreeNodeFlags_.default_open
            if result is None and not algorithm.is_clustering
            else 0,
        ):
            imgui.begin_disabled(self.jobs.busy)
            show_inputs(
                self.controls,
                dimensions=False,
                fixed_dimensions=self.controls.dimensions if dimensions else None,
            )
            if imgui.tree_node("Parameters"):
                show_parameters(self.controls, algorithm)
                imgui.tree_pop()
            imgui.end_disabled()
            open_inputs = imgui.button("Open Analysis panel")
            pos, size = imgui.get_item_rect_min(), imgui.get_item_rect_size()
            self.inputs_pixel = (pos.x + size.x / 2, pos.y + size.y / 2)
            if open_inputs:
                self.panel_source = algorithm
                hello_imgui.get_runner_params().docking_params.focus_dockable_window(
                    "Analysis"
                )
        imgui.begin_disabled(self.jobs.busy or not self.controls.features)
        if imgui.button(f"Run {algorithm}"):
            self.controls.start(self.jobs, dataset, algorithm)
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
        if result is None:
            imgui.text(f"Run {algorithm} to fit the selected features")
        elif not self.controls.matches_result(result.provenance.request):
            imgui.text_wrapped(
                f"Inputs changed; run {algorithm} to update this result."
            )
        imgui.pop_id()

    def close(self, *, wait: bool = True) -> None:
        self.jobs.close(wait=wait)
        self.plots.close()
