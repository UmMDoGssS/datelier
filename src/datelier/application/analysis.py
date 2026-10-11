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
    pending_result: Algorithm | None = None
    dataset: Dataset | None = None

    def poll(self, dataset: Dataset | None) -> bool:
        self.dataset = dataset
        revision = dataset.revision if dataset is not None else None
        completed = self.jobs.poll(revision)
        if completed and self.jobs.latest is not None:
            self.pending_result = self.jobs.latest.provenance.request.algorithm
        self.plots.poll(revision)
        return completed and isinstance(self.jobs.latest, EmbeddingResult)

    def start(self, algorithm: Algorithm) -> None:
        if self.dataset is not None:
            self.controls.start(self.jobs, self.dataset, algorithm)

    def sync_dimensions(self, plots: PlotState) -> None:
        self.controls.dimensions = plots.scatter_dimensions

    def choose_source(self, algorithm: Algorithm | None) -> None:
        if algorithm is not None and algorithm.is_clustering:
            raise ValueError(
                "Clustering colors rows; choose an embedding for coordinates"
            )
        self.source = algorithm

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
        cluster = (
            result
            if isinstance(result, ClusteringResult)
            and self.dataset is not None
            and result.revision == self.dataset.revision
            else None
        )
        if cluster is plots.cluster_result:
            return False
        plots.cluster_result = cluster
        plots.scatter_dirty = True
        return True

    def close(self, *, wait: bool = True) -> None:
        self.jobs.close(wait=wait)
        self.plots.close()
