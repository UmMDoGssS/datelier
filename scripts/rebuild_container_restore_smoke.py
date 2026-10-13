"""Fresh-process restoration of sorted, colored array record inspection."""

import argparse
import json
import subprocess
import sys
from dataclasses import replace
from pathlib import Path
from tempfile import TemporaryDirectory

import numpy as np
from imgui_bundle import hello_imgui

from datelier.application.sessions import EditorController
from datelier.gui.app import InspectionEvidence, run_gui
from datelier.gui.components.probe import GuiProbe
from datelier.inspection.presentation import NumericScale, TablePresentation
from datelier.inspection.records import InspectSettings
from datelier.pipeline import Sort


def run(root: Path, restore: bool) -> dict[str, object]:
    stage = 2 if restore else 0
    done = False
    original = (root / "arrays.npz").read_bytes()
    settings = InspectSettings(
        primary="pixels", supporting=("pixels", "values", "id"), gallery=False, focus=1
    )
    style = TablePresentation(scale=NumericScale.CUSTOM, minimum=0, maximum=20)

    def frame(
        editor: EditorController, probe: GuiProbe, evidence: InspectionEvidence
    ) -> None:
        nonlocal stage, done
        file = editor.current
        if evidence.frames > 300:
            raise AssertionError(
                (stage, editor.workspace.message, file.records.jobs.message)
            )
        if not file.inspection or editor.workspace.busy:
            return
        if stage == 0:
            file.editor.request(Sort(("priority",)))
            stage = 1
        elif stage == 1 and not file.editor.busy:
            file.records.settings = settings
            file.table.presentation.settings = style
            file.views = replace(file.views, image_height=150)
            file.images.settings = replace(
                file.images.settings,
                display=replace(file.images.settings.display, value_range=(0, 100)),
            )
            editor.choose_route("Inspect")
            stage = 2
        elif stage == 2 and evidence.frames > 25:
            page = file.pages.get(0)
            image = file.images.jobs.active
            if not page or not page.array_ready or not image:
                return
            assert page.row_ids == (1, 2, 0)
            assert [row[2].number for row in page.cells] == [10, 20, 1.5]
            assert file.records.settings == settings
            assert file.table.presentation.settings == style
            assert file.views.image_height == 150
            assert image.locator.origin.row_id == 2 and image.pixel(0, 0) == (100,)
            records = file.records.jobs.get(1)
            assert records
            card = records.cards[1]
            assert card.fields[1].cell == page.cells[1][2]
            assert card.fields[2].cell == page.cells[1][0]
            backgrounds = {
                name: [
                    value[0]
                    for key, value in probe.measurements.items()
                    if key.path[-1:] == ("background",)
                    and "records" in key.path
                    and name in key.path
                ]
                for name in ("pixels", "values", "id")
            }
            if not backgrounds["pixels"]:
                return
            assert not any(backgrounds["pixels"]) and not any(backgrounds["id"])
            assert all(backgrounds["values"])
            assert (
                not file.analysis.jobs.results and not editor.playback.snapshot.request
            )
            if restore:
                done = True
                hello_imgui.get_runner_params().app_shall_exit = True
            else:
                editor.save_workspace(root / "session.json", "", (), False, False)
                stage = 3
        elif stage == 3 and not editor.workspace.busy:
            assert editor.workspace.saved is not None
            done = True
            hello_imgui.get_runner_params().app_shall_exit = True

    evidence = run_gui(
        None if restore else root / "arrays.npz",
        initial_workspace=root / "session.json" if restore else None,
        preferences_path=root
        / ("restore-preferences.json" if restore else "preferences.json"),
        on_probe_frame=frame,
    )
    assert done and (root / "arrays.npz").read_bytes() == original
    return {
        "mode": "restore" if restore else "save",
        "frames": evidence.frames,
        "selected_columns_and_custom_range": True,
        "sorted_source_identity": True,
        "exact_pixels_and_means": True,
        "implicit_analysis_and_playback": False,
        "source_preserved": True,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--restore", type=Path)
    args = parser.parse_args()
    if args.restore:
        print(json.dumps(run(args.restore, True)))
        return
    with TemporaryDirectory(prefix="datelier-container-restore-") as directory:
        root = Path(directory)
        np.savez_compressed(
            root / "arrays.npz",
            id=np.array(["a", "long identifier", "c"]),
            pixels=np.stack(
                [np.full((2, 2), value, dtype=np.uint8) for value in (0, 50, 100)]
            ),
            values=np.array([[0, 1, 2, 3], [10, 10, 10, 10], [20, 20, 20, 20]]),
            priority=np.array([2, 0, 1]),
        )
        saved = run(root, False)
        restored = subprocess.run(
            [sys.executable, __file__, "--restore", str(root)],
            check=True,
            capture_output=True,
            text=True,
            timeout=60,
        )
        report = {
            "saved": saved,
            "restored": json.loads(restored.stdout.strip().splitlines()[-1]),
        }
        Path("/tmp/datelier-container-restore.json").write_text(
            json.dumps(report, indent=2)
        )
        print(json.dumps(report))


if __name__ == "__main__":
    main()
