"""Analysis lifetime and prepared-result coordination without GUI dependencies."""

from dataclasses import dataclass, field

from datelier.analysis.jobs import AnalysisJobs
from datelier.analysis.plots import AnalysisPlots
from datelier.analysis.types import Algorithm, ClusteringResult, EmbeddingResult
from datelier.application.analysis_settings import AnalysisSettings
from datelier.application.plot_settings import PlotState
from datelier.core.dataset import Dataset


@dataclass
class AnalysisController:
    controls: AnalysisSettings = field(default_factory=AnalysisSettings)
    jobs: AnalysisJobs = field(default_factory=AnalysisJobs)
    plots: AnalysisPlots = field(default_factory=AnalysisPlots)
    source: Algorithm | None = None
    panel_source: Algorithm | None = None

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

    def sync_dimensions(self, plots: PlotState) -> None:
        self.controls.dimensions = plots.scatter_dimensions

    def selected_algorithm(self, plots: PlotState) -> Algorithm:
        return (
            self.panel_source
            or plots.cluster_algorithm
            or self.source
            or Algorithm.KMEANS
        )

    def sync_colors(self, plots: PlotState) -> bool:
        algorithm = plots.cluster_algorithm
        result = self.jobs.results.get(algorithm) if algorithm is not None else None
        cluster = result if isinstance(result, ClusteringResult) else None
        if cluster is plots.cluster_result:
            return False
        plots.cluster_result = cluster
        plots.scatter_dirty = True
        return True

    def close(self, *, wait: bool = True) -> None:
        self.jobs.close(wait=wait)
        self.plots.close()
