"""Explicit analysis controls, completed-result switching, and provenance."""

from dataclasses import asdict, dataclass, field

from imgui_bundle import imgui

from datelier.analysis_jobs import AnalysisJobs
from datelier.analysis_types import (
    Algorithm,
    AnalysisRequest,
    ClusteringResult,
    EmbeddingResult,
    KMeansParameters,
    PCAParameters,
    Preprocessing,
    TSNEParameters,
    UMAPParameters,
)
from datelier.dataset import Dataset
from datelier.gui_analysis_form import show_inputs, show_parameters
from datelier.plotting import numeric_columns


@dataclass
class AnalysisControls:
    features: list[str] = field(default_factory=list)
    numeric: tuple[str, ...] = ()
    standardize: bool = True
    impute: bool = False
    dimensions: int = 2
    seed: int = 42
    pca_limit: int = 10_000
    pca_solver: int = 0
    pca_whiten: bool = False
    error: str = ""
    kmeans_limit: int = 10_000
    clusters: int = 3
    initializations: int = 10
    kmeans_iterations: int = 300
    center_index: int = 0
    tsne_limit: int = 2_000
    perplexity: float = 30
    tsne_iterations: int = 1_000
    tsne_auto_rate: bool = True
    tsne_rate: float = 200
    tsne_init: int = 0
    umap_limit: int = 5_000
    neighbors: int = 15
    min_distance: float = 0.1
    umap_metric: int = 0

    def bind(self, dataset: Dataset) -> None:
        self.numeric = numeric_columns(dataset)
        self.features = [n for n in self.features if n in self.numeric]

    def request(self, algorithm: Algorithm) -> AnalysisRequest:
        if algorithm == Algorithm.PCA:
            params = PCAParameters(
                ["randomized", "full"][self.pca_solver], self.pca_whiten
            )
            limit = self.pca_limit
        elif algorithm == Algorithm.KMEANS:
            params = KMeansParameters(
                self.clusters, self.initializations, self.kmeans_iterations
            )
            limit = self.kmeans_limit
        elif algorithm == Algorithm.TSNE:
            params = TSNEParameters(
                self.perplexity,
                self.tsne_iterations,
                "auto" if self.tsne_auto_rate else self.tsne_rate,
                ["pca", "random"][self.tsne_init],
            )
            limit = self.tsne_limit
        elif algorithm == Algorithm.UMAP:
            params = UMAPParameters(
                self.neighbors,
                self.min_distance,
                ["euclidean", "cosine"][self.umap_metric],
            )
            limit = self.umap_limit
        else:
            raise ValueError("This algorithm is not implemented yet")
        return AnalysisRequest(
            tuple(self.features),
            params,
            Preprocessing(self.standardize, self.impute),
            self.seed,
            limit,
            self.dimensions,
        )

    def show(
        self,
        jobs: AnalysisJobs,
        dataset: Dataset | None,
        selected: Algorithm | None = None,
    ) -> None:
        if selected is not None:
            imgui.separator_text(str(selected))
        if (
            jobs.busy
            or selected is None
            or jobs.latest is not None
            and jobs.latest.provenance.request.algorithm == selected
            or jobs.message.startswith(("Analysis failed", "Analysis cancelled"))
        ):
            imgui.text_wrapped(jobs.message)
        if jobs.busy:
            imgui.text_wrapped(f"{jobs.phase} · {jobs.elapsed:.1f}s elapsed")
            if imgui.button("Cancel analysis"):
                jobs.cancel()
        if dataset is None:
            return
        imgui.begin_disabled(jobs.busy)
        show_inputs(self, dimensions=selected != Algorithm.KMEANS)
        for algorithm in (selected,) if selected is not None else Algorithm:
            if imgui.tree_node(f"{algorithm} settings"):
                imgui.push_id(str(algorithm))
                show_parameters(self, algorithm)
                imgui.pop_id()
                imgui.tree_pop()
            imgui.begin_disabled(not self.features)
            if imgui.button(f"Run {algorithm}"):
                self.start(jobs, dataset, algorithm)
            imgui.end_disabled()
        imgui.end_disabled()
        if self.error:
            imgui.text_wrapped(self.error)
        for algorithm, result in jobs.results.items():
            if selected is not None and algorithm != selected:
                continue
            if imgui.collapsing_header(f"{algorithm} result and provenance"):
                provenance = result.provenance
                request, summary = provenance.request, provenance.input
                imgui.text_wrapped("Features: " + ", ".join(summary.used_features))
                imgui.text_wrapped(
                    f"Seed {request.seed} · sample limit {request.row_limit:,} "
                    f"· dimensions {request.dimensions}"
                )
                imgui.text_wrapped(
                    f"Rows: {summary.sampled_rows:,} sampled / "
                    f"{summary.eligible_rows:,} eligible; "
                    f"{summary.excluded_rows:,} excluded; "
                    f"{summary.imputed_cells:,} cells imputed."
                )
                imgui.text_wrapped(
                    "Removed constants: "
                    + (", ".join(summary.removed_constants) or "none")
                )
                imgui.text_wrapped(
                    "Scaling: "
                    + (
                        "standardized"
                        if request.preprocessing.standardize
                        else "original units"
                    )
                )
                imgui.text_wrapped(
                    "Missing: "
                    + (
                        "median imputation"
                        if request.preprocessing.impute
                        else "drop invalid rows"
                    )
                )
                for name, value in asdict(request.parameters).items():
                    imgui.text_wrapped(
                        f"{name.replace('_', ' ').capitalize()}: {value}"
                    )
                imgui.text_wrapped(f"Fit runtime: {provenance.runtime_seconds:.3f}s")
                imgui.text_wrapped(str(provenance.versions))
                if isinstance(result, EmbeddingResult):
                    for name, value in result.details:
                        imgui.text_wrapped(f"{name}: {value}")
                if isinstance(result, ClusteringResult) and result.fit is not None:
                    imgui.text(f"Inertia: {result.fit.inertia:.6g}")
                    self.center_index = min(self.center_index, len(result.counts) - 1)
                    _, self.center_index = imgui.combo(
                        "Center",
                        self.center_index,
                        [f"Cluster {i}" for i in range(len(result.counts))],
                    )
                    imgui.text(
                        f"Fitting rows in cluster: {result.counts[self.center_index]:,}"
                    )
                    imgui.text_wrapped(
                        "Center in fitted feature space: "
                        + str(result.fit.centers[self.center_index].tolist())
                    )
                if (
                    self.features != list(provenance.request.features)
                    or self.request(algorithm) != provenance.request
                ):
                    imgui.text_wrapped("Settings changed; run again to apply them.")

    def start(self, jobs: AnalysisJobs, dataset: Dataset, algorithm: Algorithm) -> None:
        try:
            jobs.request(dataset, self.request(algorithm))
            self.error = ""
        except ValueError as error:
            self.error = str(error)
