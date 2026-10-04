"""Completed-analysis plot switching and background preparation integration."""

from dataclasses import dataclass, field

from imgui_bundle import imgui

from datelier.analysis_jobs import AnalysisJobs
from datelier.analysis_plots import AnalysisPlots
from datelier.analysis_types import Algorithm, EmbeddingResult
from datelier.dataset import Dataset
from datelier.gui_analysis_controls import AnalysisControls
from datelier.gui_plot_controls import PlotControls
from datelier.plotting import Scatter


@dataclass
class AnalysisSession:
    controls: AnalysisControls = field(default_factory=AnalysisControls)
    jobs: AnalysisJobs = field(default_factory=AnalysisJobs)
    plots: AnalysisPlots = field(default_factory=AnalysisPlots)
    source: Algorithm | None = None

    def poll(self, dataset: Dataset | None) -> bool:
        revision = dataset.revision if dataset is not None else None
        completed = self.jobs.poll(revision)
        if completed:
            latest = self.jobs.latest
            if isinstance(latest, EmbeddingResult):
                self.source = latest.provenance.request.algorithm
        if self.source not in self.jobs.results:
            self.source = None
        self.plots.poll(revision)
        return completed and isinstance(self.jobs.latest, EmbeddingResult)

    def scatter_controls(self, dataset: Dataset, plots: PlotControls) -> Scatter | None:
        algorithms = [
            key
            for key, value in self.jobs.results.items()
            if isinstance(value, EmbeddingResult)
        ]
        index = algorithms.index(self.source) + 1 if self.source in algorithms else 0
        imgui.set_next_item_width(130)
        changed, index = imgui.combo(
            "Coordinates", index, ["Raw", *(str(a) for a in algorithms)]
        )
        if changed:
            self.source = algorithms[index - 1] if index else None
        imgui.same_line()
        if imgui.button("Analysis inputs"):
            imgui.set_window_focus("Analysis")
        imgui.same_line()
        imgui.begin_disabled(self.jobs.busy)
        if imgui.button("PCA"):
            self.controls.start(self.jobs, dataset, Algorithm.PCA)
        imgui.same_line()
        if imgui.button("t-SNE"):
            self.controls.start(self.jobs, dataset, Algorithm.TSNE)
        imgui.same_line()
        if imgui.button("UMAP"):
            self.controls.start(self.jobs, dataset, Algorithm.UMAP)
        imgui.end_disabled()
        if self.source is None:
            return None
        result = self.jobs.results.get(self.source)
        if not isinstance(result, EmbeddingResult):
            return None
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
        imgui.text_wrapped(self.plots.message)
        summary = result.provenance.input
        imgui.text_wrapped(
            f"Embedding: {summary.sampled_rows:,} sampled "
            f"of {summary.eligible_rows:,} eligible; "
            f"{summary.excluded_rows:,} excluded. "
            f"Seed {result.provenance.request.seed}."
        )
        return self.plots.active

    def close(self) -> None:
        self.jobs.close()
        self.plots.close()
