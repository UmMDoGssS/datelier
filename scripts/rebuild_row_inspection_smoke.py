"""Native row-value styling and detailed record presentation acceptance."""

import argparse
import json
from dataclasses import replace
from pathlib import Path
from tempfile import TemporaryDirectory

from imgui_bundle import hello_imgui
from PIL import Image

from datelier.application.sessions import EditorController
from datelier.gui.app import InspectionEvidence, run_gui
from datelier.gui.components.probe import GuiProbe
from datelier.workspace.preferences import Preferences, Theme, save_preferences


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--theme", default="Dark")
    parser.add_argument(
        "--mode", choices=("table", "gallery", "detail"), default="table"
    )
    args = parser.parse_args()
    verified = False
    configured = False

    def frame(
        editor: EditorController, probe: GuiProbe, evidence: InspectionEvidence
    ) -> None:
        nonlocal verified, configured
        file = editor.current
        if file.inspection and not configured:
            if args.mode == "table":
                file.selection.choose(file.inspection.dataset.revision, (0,))
            else:
                file.records.settings = replace(
                    file.records.settings, primary="id", gallery=args.mode == "gallery"
                )
                editor.choose_route("Inspect")
            configured = True
        styles = [
            value
            for key, value in probe.measurements.items()
            if key.path[-1:] == ("style",)
        ]
        fields = [key.path for key in probe.targets if key.path[-1:] == ("title",)]
        tables = [
            value
            for key, value in probe.measurements.items()
            if key.path[-1:] == ("columns",) and "records" in key.path
        ]
        ready = (
            args.mode == "table"
            or (args.mode == "gallery" and (6.0, 2.0) in tables)
            or (args.mode == "detail" and len(fields) >= 6)
        )
        if args.mode == "detail":
            image_backgrounds = [
                value[0]
                for key, value in probe.measurements.items()
                if key.path[-1:] == ("background",)
                and "records" in key.path
                and ("image" in key.path or "other_image" in key.path)
            ]
            assert not any(image_backgrounds)
            shown = {
                "image" if "image" in key.path else "other_image"
                for key, value in probe.measurements.items()
                if key.path[-2:] == ("reference", "shown")
                and value[0]
                and ("image" in key.path or "other_image" in key.path)
                and "records" in key.path
            }
            ready = ready and shown == {"image", "other_image"}
        if evidence.frames > 50 and (1.0, 1.0) in styles and ready:
            verified = True
            hello_imgui.get_runner_params().app_shall_exit = True

    with TemporaryDirectory(prefix="datelier-row-inspection-") as directory:
        source = Path(directory) / "rows.json"
        preferences = Path(directory) / "preferences.json"
        save_preferences(preferences, Preferences(theme=Theme(args.theme)))
        source.write_text(
            json.dumps(
                [
                    {
                        "amount": None,
                        "text": "A short sentence",
                        "id": 1,
                        "image": "one.png",
                        "other_image": "two.png",
                        "nested": [1, 2],
                    },
                    {
                        "amount": 2.5,
                        "text": "A longer sentence for color",
                        "id": 2,
                        "image": "two.png",
                        "other_image": "one.png",
                        "nested": [],
                    },
                    {
                        "amount": 9.0,
                        "text": None,
                        "id": 3,
                        "image": "one.png",
                        "other_image": None,
                        "nested": None,
                    },
                ]
            )
        )
        Image.new("RGB", (32, 24), (255, 0, 0)).save(Path(directory) / "one.png")
        Image.new("RGB", (24, 32), (0, 0, 255)).save(Path(directory) / "two.png")
        evidence = run_gui(
            source,
            smoke_frames=180,
            on_probe_frame=frame,
            preferences_path=preferences,
        )
    assert verified
    output = Path("/tmp/datelier-row-inspection")
    output.mkdir(exist_ok=True)
    capture = hello_imgui.final_app_window_screenshot()
    Image.fromarray(capture[:, :, :3]).save(output / f"{args.mode}-{args.theme}.png")
    report = {
        "theme": args.theme,
        "mode": args.mode,
        "frames": evidence.frames,
        "opaque_bold_null": True,
    }
    (output / f"{args.mode}-{args.theme}.json").write_text(json.dumps(report, indent=2))
    print(json.dumps(report))


if __name__ == "__main__":
    main()
