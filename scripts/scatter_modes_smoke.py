"""Live exclusive coordinate controls, unfitted states, and an explicit PCA click."""

import argparse
import json
from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import cast
from unittest.mock import patch

import numpy as np
import polars as pl
from imgui_bundle import hello_imgui, imgui
from numpy.typing import NDArray

from datelier.analysis.types import Algorithm
from datelier.gui import GuiSession, InspectionEvidence, run_gui


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path)
    parser.add_argument("--embedding", action="store_true")
    parser.add_argument("--output", type=Path, default=Path("/tmp/datelier-modes.ppm"))
    args = parser.parse_args()
    stage, entered = 0, 0
    labels: set[str] = set()
    original_combo = imgui.combo
    original_button = imgui.button

    def record_combo(label: str, index: int, choices: list[str]) -> tuple[bool, int]:
        if imgui.internal.get_current_window().name == "Explore":
            labels.add(label)
        return original_combo(label, index, choices)

    def record_button(label: str, size: tuple[float, float] = (0, 0)) -> bool:
        if imgui.internal.get_current_window().name == "Explore":
            labels.add(label)
        return original_button(label, size)

    with TemporaryDirectory(prefix="datelier-modes-") as folder:
        source = args.source or Path(folder) / "data.parquet"
        if args.source is None:
            rng = np.random.default_rng(3)
            pl.DataFrame(
                rng.normal(size=(60, 3)), schema=["x", "y", "z"]
            ).write_parquet(source)
        before = sha256(source.read_bytes()).hexdigest()

        def frame(session: GuiSession, evidence: InspectionEvidence) -> None:
            nonlocal stage, entered
            active, dashboard = session.loader.active, session.explorer.active
            if active is None or dashboard is None:
                labels.clear()
                return
            age = evidence.frames - entered
            analysis = session.analysis
            io = imgui.get_io()
            if stage == 0:
                session.exploration.tab = "Scatter"
                stage, entered = 1, evidence.frames
            elif stage == 1 and age > 10:
                assert {"##X", "##Y", "##Coordinates"} <= labels
                assert not any(label.startswith("Run ") for label in labels)
                assert not analysis.jobs.busy and not analysis.jobs.results
                analysis.source = Algorithm.PCA
                stage, entered = 2, evidence.frames
            elif stage == 2 and age > 10:
                assert "##Coordinates" in labels and not {"##X", "##Y", "##Z"} & labels
                assert "Run PCA" in labels
                assert analysis.source == Algorithm.PCA
                assert not analysis.jobs.busy and not analysis.jobs.results
                analysis.controls.features = (
                    ["age", "fare", "sibsp", "parch"]
                    if args.source
                    else ["x", "y", "z"]
                )
                stage, entered = 3, evidence.frames
            elif stage == 3 and age > 5:
                io.mouse_pos = imgui.ImVec2(*analysis.run_pixel)
                io.want_set_mouse_pos = True
                stage, entered = 4, evidence.frames
            elif stage == 4 and age > 3:
                io.add_mouse_button_event(0, True)
                stage, entered = 5, evidence.frames
            elif stage == 5 and age > 3:
                io.add_mouse_button_event(0, False)
                stage, entered = 6, evidence.frames
            elif stage == 6 and analysis.plots.active is not None and age > 15:
                assert not {"##X", "##Y", "##Z"} & labels
                assert analysis.plots.active.x_name == "PCA 1"
                analysis.source = Algorithm.TSNE
                stage, entered = 7, evidence.frames
            elif stage == 7 and age > 10:
                assert analysis.source == Algorithm.TSNE and not analysis.jobs.busy
                assert not {"##X", "##Y", "##Z"} & labels
                analysis.source = Algorithm.UMAP
                stage, entered = 8, evidence.frames
            elif stage == 8 and age > 10:
                assert analysis.source == Algorithm.UMAP and not analysis.jobs.busy
                assert set(analysis.jobs.results) == {Algorithm.PCA}
                analysis.source = None
                stage, entered = 9, evidence.frames
            elif stage == 9 and age > 10:
                assert {"##X", "##Y"} <= labels
                analysis.source = Algorithm.PCA if args.embedding else None
                io.mouse_pos = imgui.ImVec2(2, 2)
                io.want_set_mouse_pos = True
                stage, entered = 10, evidence.frames
            elif stage == 10 and age > 15:
                hello_imgui.get_runner_params().app_shall_exit = True
            labels.clear()

        with (
            patch.object(imgui, "combo", side_effect=record_combo),
            patch.object(imgui, "button", side_effect=record_button),
        ):
            evidence = run_gui(source, smoke_frames=2000, on_frame=frame)
        assert stage == 10
        assert sha256(source.read_bytes()).hexdigest() == before
        pixels = cast(NDArray[np.uint8], hello_imgui.final_app_window_screenshot())
        h, w = pixels.shape[:2]
        args.output.write_bytes(
            f"P6\n{w} {h}\n255\n".encode() + pixels[:, :, :3].tobytes()
        )
        report = {
            "frames": evidence.frames,
            "exclusive_controls": True,
            "unfitted_modes": True,
            "explicit_pca_click": True,
            "source_preserved": True,
        }
        args.output.with_suffix(".json").write_text(json.dumps(report, indent=2) + "\n")
        print(json.dumps(report))


if __name__ == "__main__":
    main()
