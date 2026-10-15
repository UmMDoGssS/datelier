"""Native exact element-mean colors and untinted Inspect array images."""

import json
from dataclasses import replace
from pathlib import Path
from tempfile import TemporaryDirectory

import numpy as np
from imgui_bundle import hello_imgui

from datelier.application.sessions import EditorController
from datelier.gui.app import InspectionEvidence, run_gui
from datelier.gui.components.probe import GuiProbe


def main() -> None:
    stage = entered = 0
    done = False

    def frame(
        editor: EditorController, probe: GuiProbe, evidence: InspectionEvidence
    ) -> None:
        nonlocal stage, entered, done
        file = editor.current
        page = file.pages.get(0) if file.inspection else None
        if stage == 0 and page and page.array_ready:
            assert [row[1].number for row in page.cells] == [0, 50, 100]
            assert [row[2].number for row in page.cells] == [1.5, 10, 20]
            assert all(row[0].text_length is None for row in page.cells)
            file.records.settings = replace(
                file.records.settings,
                primary="id",
                supporting=("pixels", "values", "id"),
            )
            editor.choose_route("Inspect")
            stage, entered = 1, evidence.frames
        if stage == 1 and evidence.frames - entered > 20:
            image_backgrounds = [
                value[0]
                for key, value in probe.measurements.items()
                if key.path[-1:] == ("background",)
                and "records" in key.path
                and "pixels" in key.path
            ]
            array_means = [
                value[0]
                for key, value in probe.measurements.items()
                if key.path[-1:] == ("mean",)
                and "records" in key.path
                and "values" in key.path
            ]
            backgrounds = [
                value[0]
                for key, value in probe.measurements.items()
                if key.path[-1:] == ("background",)
                and "records" in key.path
                and "values" in key.path
            ]
            if image_backgrounds and array_means:
                assert not any(image_backgrounds) and any(backgrounds)
                assert 1.5 in array_means
                assert (
                    not file.analysis.jobs.results
                    and not editor.playback.snapshot.request
                )
                done = True
                hello_imgui.get_runner_params().app_shall_exit = True

    with TemporaryDirectory(prefix="datelier-container-colors-") as directory:
        source = Path(directory) / "arrays.npz"
        np.savez_compressed(
            source,
            id=np.array(["a", "long identifier", "c"]),
            pixels=np.stack(
                [np.full((2, 2), value, dtype=np.uint8) for value in (0, 50, 100)]
            ),
            values=np.array(
                [
                    [0.0, 1.0, 2.0, 3.0],
                    [10.0, 10.0, 10.0, 10.0],
                    [20.0, 20.0, 20.0, 20.0],
                ]
            ),
        )
        original = source.read_bytes()
        evidence = run_gui(source, smoke_frames=240, on_probe_frame=frame)
        assert done and source.read_bytes() == original
    report = {
        "frames": evidence.frames,
        "exact_element_means": True,
        "identifiers_neutral": True,
        "inspect_image_backgrounds": False,
        "generic_arrays_colored": True,
        "source_preserved": True,
    }
    Path("/tmp/datelier-container-colors.json").write_text(json.dumps(report, indent=2))
    print(json.dumps(report))


if __name__ == "__main__":
    main()
