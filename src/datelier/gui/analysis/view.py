"""Analysis is composed inside Relationships context with explicit result opening."""

from collections.abc import Callable
from dataclasses import asdict

from imgui_bundle import imgui

from datelier.analysis.types import Algorithm, AnalysisResult, ClusteringResult
from datelier.application.analysis import AnalysisController
from datelier.application.columns import ColumnChoice, MultiSelection
from datelier.gui.analysis.parameters import AlgorithmEditors, boolean, integer
from datelier.gui.components.actions import CommandButton, JobFeedback, JobSnapshot
from datelier.gui.components.base import Component, Container, FrameContext
from datelier.gui.components.columns import ColumnPicker
from datelier.gui.components.facts import FactsTable
from datelier.gui.components.fields import ChoiceField


class Provenance(Component):
    def __init__(
        self, model: AnalysisController, selected: Callable[[], Algorithm]
    ) -> None:
        super().__init__("provenance")
        self.model, self.selected = model, selected

    def render(self, frame: FrameContext) -> None:
        result = self.model.jobs.results.get(self.selected())
        if result is None:
            return
        provenance = result.provenance
        request, summary = provenance.request, provenance.input
        stale = (
            self.model.dataset is None or result.revision != self.model.dataset.revision
        )
        changed = not self.model.controls.matches_result(request)
        imgui.separator_text("Result and provenance")
        if stale:
            imgui.text_wrapped("Result belongs to an earlier data revision.")
        if changed:
            imgui.text_wrapped("Settings changed since this result was fitted.")
        imgui.text_wrapped("Features: " + ", ".join(summary.used_features))
        imgui.text_wrapped(
            f"{summary.sampled_rows:,} fitted / {summary.eligible_rows:,} eligible · "
            f"{summary.excluded_rows:,} excluded · "
            f"{summary.imputed_cells:,} cells imputed"
        )
        imgui.text_wrapped(
            f"Seed {request.seed} · sample limit {request.row_limit:,} · "
            f"{request.dimensions} dimensions · {provenance.runtime_seconds:.3f}s"
        )
        imgui.text_wrapped(
            "Removed constants: " + (", ".join(summary.removed_constants) or "none")
        )
        imgui.text_wrapped(
            "Standardized" if request.preprocessing.standardize else "Original units"
        )
        imgui.text_wrapped(
            "Median imputation"
            if request.preprocessing.impute
            else "Invalid rows excluded"
        )
        for name, value in asdict(request.method).items():
            imgui.text_wrapped(f"{name.replace('_', ' ')}: {value}")
        for name, version in provenance.versions:
            imgui.text_wrapped(f"{name} {version}")
        for name, value in result.details:
            imgui.text_wrapped(f"{name}: {value}")


class ClusterFacts(Container):
    def __init__(self, prepared: Callable[[], AnalysisResult | None]) -> None:
        self.prepared = prepared
        self.center = 0
        super().__init__(
            "clusters",
            (
                FactsTable("counts", ("Cluster", "Rows"), self.counts, 100),
                FactsTable(
                    "center", ("Feature", "Center in fitted units"), self.values, 130
                ),
            ),
        )

    def counts(self) -> tuple[tuple[object, ...], ...]:
        result = self.prepared()
        return (
            tuple(enumerate(result.counts))
            if isinstance(result, ClusteringResult)
            else ()
        )

    def values(self) -> tuple[tuple[object, ...], ...]:
        result = self.prepared()
        if not isinstance(result, ClusteringResult) or result.fit is None:
            return ()
        fit = result.fit
        self.center = min(self.center, len(fit.centers) - 1)
        return tuple(
            zip(fit.model.features, fit.centers[self.center].tolist(), strict=True)
        )

    def render(self, frame: FrameContext) -> None:
        result = self.prepared()
        if not isinstance(result, ClusteringResult):
            return
        imgui.text(
            f"{len(result.counts)} clusters · {result.noise_count:,} noise points"
        )
        if result.fit is not None:
            imgui.text(f"Inertia {result.fit.inertia:.8g}")
            imgui.set_next_item_width(-1)
            _, self.center = imgui.combo(
                "Cluster center",
                self.center,
                [str(i) for i in range(len(result.fit.centers))],
            )
        super().render(frame)


class AnalysisSettingsView(Container):
    def __init__(
        self, model: AnalysisController, open_result: Callable[[Algorithm], None]
    ) -> None:
        self.model = model

        def selected() -> Algorithm:
            return model.panel_source or Algorithm.PCA

        controls = model.controls
        super().__init__(
            "analysis",
            (
                ChoiceField(
                    "algorithm",
                    "Algorithm",
                    tuple(Algorithm),
                    selected,
                    lambda value: setattr(model, "panel_source", value),
                ),
                ColumnPicker(
                    "features",
                    "Analysis features (up to 128)",
                    lambda: tuple(
                        ColumnChoice(n, "Numeric", True) for n in controls.numeric
                    ),
                    lambda: tuple(controls.features),
                    lambda names: setattr(controls, "features", list(names)),
                    MultiSelection(limit=128),
                ),
                boolean(controls, "standardize", "Standardize features"),
                boolean(controls, "impute", "Fill missing values with median"),
                integer(controls, "seed", "Random seed", minimum=0, maximum=2**32 - 1),
                AlgorithmEditors(controls, selected),
                CommandButton(
                    "run",
                    "Run analysis",
                    lambda: model.start(selected()),
                    lambda: (
                        model.dataset is not None
                        and bool(controls.features)
                        and not model.jobs.busy
                    ),
                ),
                JobFeedback(
                    "job",
                    lambda: JobSnapshot(
                        model.jobs.message,
                        model.jobs.busy,
                        f"{model.jobs.phase} · {model.jobs.elapsed:.1f}s"
                        if model.jobs.busy
                        else controls.error,
                    ),
                    model.jobs.cancel,
                ),
                CommandButton(
                    "open-result",
                    "Open result",
                    lambda: open_result(model.pending_result or selected()),
                    lambda: (model.pending_result or selected()) in model.jobs.results,
                ),
                Provenance(model, selected),
                ClusterFacts(lambda: model.jobs.results.get(selected())),
            ),
        )
