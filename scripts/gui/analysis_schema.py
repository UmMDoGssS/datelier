"""Render every method schema and edit representative fields through native input."""

import json
from pathlib import Path
from tempfile import TemporaryDirectory

import numpy as np
import polars as pl
from imgui_bundle import hello_imgui, imgui

from datelier.analysis.types import (
    Algorithm,
    KMeansParameters,
    PCAParameters,
    TSNEParameters,
)
from datelier.application.sessions import EditorController
from datelier.gui.app import InspectionEvidence, run_gui
from datelier.gui.components.probe import GuiProbe
from scripts.support.input import NativeInput, NativeText


def main() -> None:
    with TemporaryDirectory(prefix="datelier-analysis-schema-") as directory:
        path = Path(directory) / "source.csv"
        rng = np.random.default_rng(2)
        pl.DataFrame({n: rng.normal(size=120) for n in ("x", "y", "z")}).write_csv(path)
        original = path.read_bytes()
        pointer, text = NativeInput(), NativeText()
        algorithms = tuple(Algorithm)
        stage = entered = 0
        forms: list[str] = []
        complete = False

        def frame(
            editor: EditorController, probe: GuiProbe, evidence: InspectionEvidence
        ) -> None:
            nonlocal stage, entered, complete
            file = editor.active
            controls = file.analysis.controls
            count = evidence.frames
            age = count - entered
            if count > 3000:
                raise AssertionError((stage, tuple(key.path for key in probe.targets)))
            if pointer.advance(count) or text.advance(count):
                return
            if not file.explorer.active or count < 20:
                return
            assert file.analysis.jobs.latest is None and not file.analysis.jobs.busy
            if stage < len(algorithms):
                algorithm = algorithms[stage]
                editor.choose_route("Relationships")
                if file.analysis.panel_source != algorithm:
                    file.analysis.panel_source = algorithm
                    entered = count
                    return
                if age < 6:
                    return
                builder = controls.algorithms[algorithm]
                expected: set[tuple[str, ...]] = {("limit", "value")}
                for descriptor in builder.schema:
                    if descriptor.visible(builder):
                        expected.add(
                            (descriptor.name, "automatic", "value")
                            if descriptor.automatic
                            else (descriptor.name, "value")
                        )
                actual = {
                    key.path[key.path.index(algorithm.value) + 1 :]
                    for key in probe.targets
                    if algorithm.value in key.path and "parameters" in key.path
                }
                assert expected <= actual, (algorithm, expected, actual)
                forms.append(algorithm.value)
                stage, entered = stage + 1, count
                return
            step = stage - len(algorithms)
            if step == 0:
                file.analysis.panel_source = Algorithm.PCA
                if age > 6 and pointer.click(probe, ("PCA", "whiten", "value"), count):
                    stage, entered = stage + 1, count
            elif step == 1:
                assert controls.algorithms[Algorithm.PCA] == PCAParameters(whiten=True)
                file.analysis.panel_source = Algorithm.TSNE
                if age > 6 and pointer.click(
                    probe, ("t-SNE", "learning_rate", "automatic", "value"), count
                ):
                    stage, entered = stage + 1, count
            elif step == 2:
                params = controls.algorithms[Algorithm.TSNE]
                assert (
                    isinstance(params, TSNEParameters) and params.learning_rate == 200
                )
                if pointer.click(
                    probe, ("t-SNE", "learning_rate", "manual", "value"), count
                ):
                    stage, entered = stage + 1, count
            elif step == 3:
                text.start("55", count)
                stage, entered = stage + 1, count
            elif step == 4:
                params = controls.algorithms[Algorithm.TSNE]
                assert isinstance(params, TSNEParameters) and params.learning_rate == 55
                if pointer.click(
                    probe, ("t-SNE", "learning_rate", "automatic", "value"), count
                ):
                    stage, entered = stage + 1, count
            elif step == 5:
                params = controls.algorithms[Algorithm.TSNE]
                assert (
                    isinstance(params, TSNEParameters)
                    and params.learning_rate == "auto"
                )
                assert (
                    pointer.find(probe, ("t-SNE", "learning_rate", "manual", "value"))
                    is None
                )
                if pointer.click(
                    probe, ("t-SNE", "learning_rate", "automatic", "value"), count
                ):
                    stage, entered = stage + 1, count
            elif step == 6:
                params = controls.algorithms[Algorithm.TSNE]
                assert isinstance(params, TSNEParameters) and params.learning_rate == 55
                file.analysis.panel_source = Algorithm.MEAN_SHIFT
                if age > 6 and pointer.click(
                    probe, ("Mean shift", "automatic_bandwidth", "value"), count
                ):
                    stage, entered = stage + 1, count
            elif step == 7:
                assert pointer.find(probe, ("Mean shift", "bandwidth", "value"))
                assert pointer.find(probe, ("Mean shift", "quantile", "value")) is None
                file.analysis.panel_source = Algorithm.KMEANS
                stage, entered = stage + 1, count
            elif step == 8:
                if age > 6 and pointer.click(
                    probe, ("K-means", "clusters", "value"), count
                ):
                    stage, entered = stage + 1, count
            elif step == 9:
                text.start("4", count)
                stage, entered = stage + 1, count
            elif step == 10:
                params = controls.algorithms[Algorithm.KMEANS]
                assert isinstance(params, KMeansParameters) and params.clusters == 4
                file.analysis.panel_source = Algorithm.PCA
                stage, entered = stage + 1, count
            elif step == 11:
                if age > 6 and pointer.click(probe, ("PCA", "solver", "value"), count):
                    stage, entered = stage + 1, count
            elif step == 12 and age > 4:
                imgui.get_io().add_key_event(imgui.Key.end, True)
                stage, entered = stage + 1, count
            elif step == 13 and age > 4:
                imgui.get_io().add_key_event(imgui.Key.end, False)
                imgui.get_io().add_key_event(imgui.Key.enter, True)
                stage, entered = stage + 1, count
            elif step == 14 and age > 4:
                imgui.get_io().add_key_event(imgui.Key.enter, False)
                stage, entered = stage + 1, count
            elif step == 15 and age > 4:
                assert controls.algorithms[Algorithm.PCA] == PCAParameters(
                    solver="full", whiten=True
                )
                assert path.read_bytes() == original
                complete = True
                hello_imgui.get_runner_params().app_shall_exit = True

        evidence = run_gui(path, on_probe_frame=frame)
        assert complete and len(forms) == 26
        print(
            json.dumps(
                {
                    "frames": evidence.frames,
                    "frame_p95_ms": float(
                        np.percentile(evidence.frame_intervals_ms, 95)
                    ),
                    "schemas_rendered": forms,
                    "native_boolean_and_numeric_edits": True,
                    "native_integer_and_choice_edits": True,
                    "automatic_manual_draft_retained": True,
                    "conditional_visibility": True,
                    "no_implicit_analysis": True,
                    "source_preserved": True,
                }
            )
        )


if __name__ == "__main__":
    main()
