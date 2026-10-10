"""Analysis configuration and result components with an injected typed draft."""

from dataclasses import asdict, dataclass

from imgui_bundle import imgui

from datelier.analysis.jobs import AnalysisJobs
from datelier.analysis.types import Algorithm, ClusteringResult, EmbeddingResult
from datelier.application.analysis_settings import AnalysisSettings
from datelier.core.dataset import Dataset
from datelier.gui.analysis.form import AlgorithmParameters, AnalysisInputs
from datelier.gui.components.base import BoundView, FrameContext
from datelier.gui.components.probe import GuiProbe, ViewScope


@dataclass(frozen=True)
class AnalysisFormBinding:
    settings: AnalysisSettings
    jobs: AnalysisJobs
    dataset: Dataset | None
    selected: Algorithm | None = None
    fixed_dimensions: int | None = None


class AnalysisForm(BoundView[AnalysisFormBinding]):
    def __init__(self) -> None:
        self.inputs = AnalysisInputs()
        self.parameters = AlgorithmParameters()

    def show(
        self,
        settings: AnalysisSettings,
        jobs: AnalysisJobs,
        dataset: Dataset | None,
        selected: Algorithm | None = None,
        *,
        fixed_dimensions: int | None = None,
    ) -> None:
        self.bind_view(
            AnalysisFormBinding(settings, jobs, dataset, selected, fixed_dimensions)
        )
        self.render(
            FrameContext(
                ViewScope("", revision=dataset.revision if dataset else None),
                GuiProbe(),
            )
        )

    def draw(self, binding: AnalysisFormBinding, frame: FrameContext) -> None:
        settings, jobs, dataset = binding.settings, binding.jobs, binding.dataset
        selected, fixed_dimensions = binding.selected, binding.fixed_dimensions
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
        self.inputs.show(
            settings,
            dimensions=selected is None or not selected.is_clustering,
            fixed_dimensions=fixed_dimensions
            if selected is None or not selected.is_clustering
            else None,
        )
        for algorithm in (selected,) if selected is not None else Algorithm:
            if imgui.tree_node(f"{algorithm} settings"):
                imgui.push_id(str(algorithm))
                self.parameters.show(settings, algorithm)
                imgui.pop_id()
                imgui.tree_pop()
            imgui.begin_disabled(not settings.features)
            if imgui.button(f"Run {algorithm}"):
                settings.start(jobs, dataset, algorithm)
            imgui.end_disabled()
        imgui.end_disabled()
        if settings.error:
            imgui.text_wrapped(settings.error)
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
                if isinstance(result, ClusteringResult):
                    imgui.text(
                        f"{len(result.counts)} clusters · "
                        f"{result.noise_count:,} noise points"
                    )
                    for name, value in result.details:
                        imgui.text_wrapped(f"{name}: {value}")
                if isinstance(result, ClusteringResult) and result.fit is not None:
                    imgui.text(f"Inertia: {result.fit.inertia:.6g}")
                    settings.center_index = min(
                        settings.center_index, len(result.counts) - 1
                    )
                    _, settings.center_index = imgui.combo(
                        "Center",
                        settings.center_index,
                        [f"Cluster {i}" for i in range(len(result.counts))],
                    )
                    imgui.text(
                        "Fitting rows in cluster: "
                        f"{result.counts[settings.center_index]:,}"
                    )
                    imgui.text_wrapped(
                        "Center in fitted feature space: "
                        + str(result.fit.centers[settings.center_index].tolist())
                    )
                if not settings.matches_result(provenance.request):
                    imgui.text_wrapped("Settings changed; run again to apply them.")
