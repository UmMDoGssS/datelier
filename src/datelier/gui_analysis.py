"""Explicit analysis controls, completed-result switching, and provenance."""

from dataclasses import asdict, dataclass, field

from imgui_bundle import imgui

from datelier.analysis_jobs import AnalysisJobs
from datelier.analysis_plots import AnalysisPlots
from datelier.analysis_types import (
    Algorithm,
    AnalysisRequest,
    EmbeddingResult,
    PCAParameters,
    Preprocessing,
)
from datelier.dataset import Dataset
from datelier.gui_plot_controls import PlotControls
from datelier.plotting import Scatter, numeric_columns


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

    def bind(self, dataset: Dataset) -> None:
        self.numeric = numeric_columns(dataset)
        self.features = [n for n in self.features if n in self.numeric]

    def request(self, algorithm: Algorithm) -> AnalysisRequest:
        if algorithm != Algorithm.PCA:
            raise ValueError("This algorithm is not implemented yet")
        return AnalysisRequest(
            tuple(self.features),
            PCAParameters(["randomized", "full"][self.pca_solver], self.pca_whiten),
            Preprocessing(self.standardize, self.impute),
            self.seed,
            self.pca_limit,
            self.dimensions,
        )

    def show(self, jobs: AnalysisJobs, dataset: Dataset | None) -> None:
        imgui.text_wrapped(jobs.message)
        if jobs.busy:
            imgui.text_wrapped(f"{jobs.phase} · {jobs.elapsed:.1f}s elapsed")
            if imgui.button("Cancel analysis"):
                jobs.cancel()
        if dataset is None:
            return
        imgui.text_wrapped(
            "Choose analysis inputs independently of raw scatter axes. "
            "Loading data never starts analysis."
        )
        imgui.push_item_width(110)
        imgui.begin_disabled(jobs.busy)
        if imgui.button("Select numeric features"):
            self.features = list(self.numeric[:128])
        imgui.same_line()
        if imgui.button("Clear features"):
            self.features.clear()
        if imgui.begin_child("Analysis features", (0, 110)):
            for name in self.numeric:
                chosen = name in self.features
                imgui.begin_disabled(not chosen and len(self.features) >= 128)
                changed, checked = imgui.checkbox(name, chosen)
                imgui.end_disabled()
                if changed:
                    if checked:
                        self.features.append(name)
                    else:
                        self.features.remove(name)
        imgui.end_child()
        _, self.standardize = imgui.checkbox(
            "Standardize analysis features", self.standardize
        )
        _, self.impute = imgui.checkbox("Impute missing with median", self.impute)
        changed, dims = imgui.combo(
            "Output dimensions", self.dimensions - 2, ["2", "3"]
        )
        if changed:
            self.dimensions = dims + 2
        _, self.seed = imgui.input_int("Random seed", self.seed)
        _, self.pca_limit = imgui.input_int("PCA rows (max 100k)", self.pca_limit)
        _, self.pca_solver = imgui.combo(
            "PCA solver", self.pca_solver, ["randomized", "full"]
        )
        _, self.pca_whiten = imgui.checkbox("PCA whitening", self.pca_whiten)
        if imgui.button("Run PCA"):
            self.start(jobs, dataset, Algorithm.PCA)
        imgui.end_disabled()
        imgui.pop_item_width()
        if self.error:
            imgui.text_wrapped(self.error)
        for algorithm, result in jobs.results.items():
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
        if imgui.button("Analysis settings"):
            imgui.set_window_focus("Analysis")
        imgui.same_line()
        imgui.begin_disabled(self.jobs.busy)
        if imgui.button("PCA"):
            self.controls.start(self.jobs, dataset, Algorithm.PCA)
        imgui.end_disabled()
        if self.source is None:
            return None
        result = self.jobs.results.get(self.source)
        if not isinstance(result, EmbeddingResult):
            return None
        color = (
            plots.color_columns[plots.color_index - 1] if plots.color_index else None
        )
        self.plots.ensure(dataset, result, plots.point_limit, color)
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
