"""Native View-menu recovery for hidden Explore and source-browser panels."""

import json
from pathlib import Path
from tempfile import TemporaryDirectory

from imgui_bundle import hello_imgui
from rebuild_input import NativeInput

from datelier.application.sessions import EditorController
from datelier.gui.app import InspectionEvidence, run_gui
from datelier.gui.components.probe import GuiProbe
from datelier.workspace.preferences import Preferences, save_preferences


def main() -> None:
    native = NativeInput()
    stage = entered = 0
    done = False

    def frame(
        editor: EditorController, probe: GuiProbe, evidence: InspectionEvidence
    ) -> None:
        nonlocal stage, entered, done
        if evidence.frames > 400:
            raise AssertionError((stage, [key.path for key in probe.targets]))
        if native.advance(evidence.frames):
            return
        if not editor.current.inspection or evidence.frames - entered < 5:
            return
        canvas = native.find(probe, ("workbench", "canvas", "clip-start"))
        browser = native.find(probe, ("workbench", "source", "clip-start"))
        suffix: tuple[str, ...] | None = None
        if stage == 0 and evidence.frames > 20:
            assert canvas is None and browser is None
            suffix = ("menus", "View", "menu")
        elif stage == 1:
            assert all(
                native.find(probe, ("menus", "View", name, "run"))
                for name in ("source", "canvas", "context", "table")
            )
            suffix = ("menus", "View", "canvas", "run")
        elif stage == 2 and canvas:
            assert browser is None
            suffix = ("menus", "View", "menu")
        elif stage == 3:
            suffix = ("menus", "View", "source", "run")
        elif stage == 4 and canvas and browser:
            suffix = ("menus", "View", "menu")
        elif stage == 5:
            suffix = ("menus", "View", "canvas", "run")
        elif stage == 6 and canvas is None:
            assert browser
            suffix = ("menus", "View", "menu")
        elif stage == 7:
            suffix = ("menus", "View", "canvas", "run")
        elif stage == 8 and canvas and browser:
            assert not editor.current.analysis.jobs.results
            assert editor.playback.snapshot.request is None
            done = True
            hello_imgui.get_runner_params().app_shall_exit = True
        if suffix and (point := native.find(probe, suffix)):
            native.click_point(point, evidence.frames)
            stage, entered = stage + 1, evidence.frames

    with TemporaryDirectory(prefix="datelier-panel-views-") as directory:
        source = Path(directory) / "data.csv"
        source.write_text("x,y\n1.0,2.0\n3.0,4.0\n")
        original = source.read_bytes()
        preferences = Path(directory) / "preferences.json"
        save_preferences(
            preferences, Preferences(hidden_windows=("Explore", "Source browser"))
        )
        evidence = run_gui(source, preferences_path=preferences, on_probe_frame=frame)
        assert done and source.read_bytes() == original
    report = {
        "frames": evidence.frames,
        "all_panels_in_view_menu": True,
        "hidden_explore_and_browser_restored": True,
        "explore_toggle_reversible": True,
        "source_preserved": True,
    }
    Path("/tmp/datelier-panel-views.json").write_text(json.dumps(report, indent=2))
    print(json.dumps(report))


if __name__ == "__main__":
    main()
