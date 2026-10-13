"""Native row-value styling and detailed record presentation acceptance."""

import argparse
import json
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
    args = parser.parse_args()
    verified = False

    def frame(
        editor: EditorController, probe: GuiProbe, evidence: InspectionEvidence
    ) -> None:
        nonlocal verified
        styles = [
            value
            for key, value in probe.measurements.items()
            if key.path[-1:] == ("style",)
        ]
        if evidence.frames > 30 and (1.0, 1.0) in styles:
            verified = True
            hello_imgui.get_runner_params().app_shall_exit = True

    with TemporaryDirectory(prefix="datelier-row-inspection-") as directory:
        source = Path(directory) / "rows.json"
        preferences = Path(directory) / "preferences.json"
        save_preferences(preferences, Preferences(theme=Theme(args.theme)))
        source.write_text(
            json.dumps(
                [
                    {"id": 1, "amount": None, "text": "A short sentence"},
                    {"id": 2, "amount": 2.5, "text": "A longer sentence for color"},
                    {"id": 3, "amount": 9.0, "text": None},
                ]
            )
        )
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
    Image.fromarray(capture[:, :, :3]).save(output / f"table-{args.theme}.png")
    report = {"theme": args.theme, "frames": evidence.frames, "opaque_bold_null": True}
    (output / f"table-{args.theme}.json").write_text(json.dumps(report, indent=2))
    print(json.dumps(report))


if __name__ == "__main__":
    main()
