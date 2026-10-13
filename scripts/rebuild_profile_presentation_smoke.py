"""Native wide profile facts and all five distinctly colored comparison modes."""

import argparse
import json
from pathlib import Path
from tempfile import TemporaryDirectory

import numpy as np
import polars as pl
from imgui_bundle import hello_imgui
from PIL import Image

from datelier.application.sessions import EditorController
from datelier.gui.app import InspectionEvidence, run_gui
from datelier.gui.components.probe import GuiProbe
from datelier.workspace.preferences import Preferences, Theme, save_preferences


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--theme", choices=tuple(Theme), default=Theme.DARK)
    args = parser.parse_args()
    mode = entered = 0
    configured = done = False
    names = ("alpha", "beta", "gamma")

    def frame(
        editor: EditorController, probe: GuiProbe, evidence: InspectionEvidence
    ) -> None:
        nonlocal configured, done, mode, entered
        file = editor.current
        if file.inspection and not configured:
            file.profiles.choose(names)
            file.profiles.height = 180
            configured = True
            entered = evidence.frames
        group = file.explorer.profiles.active
        facts = [
            value
            for key, value in probe.measurements.items()
            if key.path[-2:] == ("statistics", "shape")
        ]
        plots = [key.path for key in probe.targets if key.path[-1:] == ("canvas",)]
        rendered = [
            value
            for key, value in probe.measurements.items()
            if key.path[-2:] == ("statistics", "rendered")
        ]
        if group and tuple(p.name for p in group.profiles.columns) == names:
            assert len(group.tables[0].rows) == 3 and len(group.tables[0].headers) == 18
            if (
                (3.0, 18.0) in facts
                and (3.0, 3.0) in rendered
                and plots
                and evidence.frames - entered >= 10
            ):
                if mode < 4:
                    mode += 1
                    file.profiles.mode = mode
                    entered = evidence.frames
                else:
                    assert not file.analysis.jobs.results
                    assert not editor.playback.snapshot.request
                    done = True
                    hello_imgui.get_runner_params().app_shall_exit = True

    with TemporaryDirectory(prefix="datelier-profile-presentation-") as directory:
        root = Path(directory)
        source, preferences = root / "data.csv", root / "preferences.json"
        rng = np.random.default_rng(42)
        pl.DataFrame(
            {
                "alpha": rng.normal(0, 1, 800),
                "beta": rng.normal(1, 1.5, 800),
                "gamma": rng.normal(2, 0.6, 800),
            }
        ).write_csv(source)
        original = source.read_bytes()
        save_preferences(preferences, Preferences(theme=Theme(args.theme)))
        evidence = run_gui(
            source, smoke_frames=300, on_probe_frame=frame, preferences_path=preferences
        )
        assert done and source.read_bytes() == original
    output = Path("/tmp/datelier-profile-presentation")
    output.mkdir(exist_ok=True)
    Image.fromarray(hello_imgui.final_app_window_screenshot()[:, :, :3]).save(
        output / f"profiles-{args.theme}.png"
    )
    report = {
        "theme": args.theme,
        "frames": evidence.frames,
        "stats_rows": 3,
        "stats_columns": 18,
        "plot_modes": 5,
        "source_preserved": True,
    }
    (output / f"profiles-{args.theme}.json").write_text(json.dumps(report, indent=2))
    print(json.dumps(report))


if __name__ == "__main__":
    main()
