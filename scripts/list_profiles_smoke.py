"""Render flattened list charts, length/shape tables and restored profile selection."""

import argparse
import json
import subprocess
import sys
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from imgui_bundle import hello_imgui, imgui
from PIL import Image

from datelier.gui.app import InspectionEvidence, run_gui
from datelier.gui.editor_session import EditorSession
from datelier.gui.plots.axes import AxisControls
from datelier.gui.profiles import view
from datelier.gui.tabs import EditorTabs
from datelier.plotting.distributions import Comparison


def run(root: Path, output: Path, *, restore: bool) -> dict[str, object]:
    stage = entered = 0
    tables: set[str] = set()
    charts: set[int] = set()
    categorical = False
    original_table, original_plot = imgui.begin_table, view.show_comparison
    workspace = root / "session.datelier.json"

    def table(
        label: str,
        count: int,
        flags: int = 0,
        size: imgui.ImVec2 | None = None,
        inner_width: float = 0,
    ) -> bool:
        result = original_table(
            label, count, flags, size or imgui.ImVec2(), inner_width
        )
        if result and label in ("Profile statistics", "List statistics", "List shapes"):
            tables.add(label)
        return result

    def plot(
        comparison: Comparison,
        mode: int,
        fit: bool,
        *,
        title: str = "Column comparison",
        details: bool = True,
        height: float = 220,
        axes: AxisControls | None = None,
        colored: bool = False,
        count_label: str = "Rows",
    ) -> bool:
        result = original_plot(
            comparison,
            mode,
            fit,
            title=title,
            details=details,
            height=height,
            axes=axes,
            colored=colored,
            count_label=count_label,
        )
        if result:
            charts.add(mode)
        return result

    def frame(
        editor: EditorSession, tabs: EditorTabs, evidence: InspectionEvidence
    ) -> None:
        nonlocal stage, entered, categorical
        file = editor.active
        if file.loader.active is None:
            ready = next((f for f in editor.files if f.loader.active), None)
            if ready and restore:
                editor.activate(ready.identity)
            return
        profile_view = file.exploration.profile
        age = evidence.frames - entered
        if stage == 0:
            if restore:
                assert profile_view.selection.columns == ("numbers",)
                assert profile_view.mode == 0
                assert not file.text.jobs.busy and not file.analysis.jobs.results
            file.exploration.tab = "Profiles"
            profile_view.selection.columns = ("numbers",) if restore else ("words",)
            profile_view.area.expanded = True
            stage, entered = (2 if restore else 1), evidence.frames
            hello_imgui.get_runner_params().docking_params.focus_dockable_window(
                "Explore"
            )
        elif stage == 1 and age > 15 and len(tables) == 3:
            group = file.explorer.profiles.active
            if group is None or group.profiles.columns[0].name != "words":
                return
            profile = group.profiles.columns[0]
            assert profile.distribution.labels == ("a", "b", "c")
            assert profile.distribution.counts == (2, 2, 1)
            assert profile.null_count == 1
            categorical = True
            tables.clear()
            profile_view.selection.columns = ("numbers",)
            profile_view.mode = 0
            stage, entered = 2, evidence.frames
        elif stage == 2 and age > 20 and len(tables) == 3:
            group = file.explorer.profiles.active
            if group is None or group.profiles.columns[0].name != "numbers":
                return
            profile = group.profiles.columns[0]
            assert profile.statistics and profile.statistics.mean == 4.5
            lists = profile.list_statistics
            assert lists is not None
            assert (lists.elements, lists.null_elements) == (9, 1)
            assert (lists.rectangular, lists.ragged, lists.unknown) == (1, 1, 2)
            if profile_view.mode not in charts:
                return
            if not restore and profile_view.mode < 4:
                profile_view.mode += 1
                entered = evidence.frames
            elif restore:
                stage = 4
                hello_imgui.get_runner_params().app_shall_exit = True
            else:
                profile_view.mode = 0
                editor.save_workspace(workspace)
                stage, entered = 3, evidence.frames
        elif stage == 3 and age > 15 and editor.workspace_jobs.saved is not None:
            stage = 4
            hello_imgui.get_runner_params().app_shall_exit = True

    with (
        patch.object(imgui, "begin_table", new=table),
        patch.object(view, "show_comparison", new=plot),
    ):
        evidence = run_gui(
            None if restore else root / "source.json",
            initial_workspace=workspace if restore else None,
            smoke_frames=400,
            on_editor_frame=frame,
            preferences_path=root / ("restore-prefs.json" if restore else "prefs.json"),
        )
    assert stage == 4 and len(tables) == 3, (stage, tables, charts)
    assert restore or categorical and charts == set(range(5))
    output.mkdir(parents=True, exist_ok=True)
    Image.fromarray(hello_imgui.final_app_window_screenshot()[:, :, :3]).save(
        output / ("profiles-restored.png" if restore else "profiles.png")
    )
    return {
        "frames": evidence.frames,
        "restore": restore,
        "tables": sorted(tables),
        "numeric_modes": sorted(charts),
        "categorical": categorical,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--restore", type=Path)
    parser.add_argument(
        "--output", type=Path, default=Path("/tmp/datelier-list-profiles")
    )
    args = parser.parse_args()
    if args.restore:
        print(json.dumps(run(args.restore, args.output, restore=True)))
        return
    with TemporaryDirectory(prefix="datelier-list-profiles-") as directory:
        root = Path(directory)
        source = root / "source.json"
        numbers = [[[1, 2], [3, 4]], [[5], [6, 7]], [], None, [None, [8, None]]]
        words = [["a", "b", "a"], [], None, ["b"], [None, "c"]]
        content = json.dumps(
            [
                {"id": i, "numbers": n, "words": w}
                for i, (n, w) in enumerate(zip(numbers, words, strict=True))
            ]
        )
        source.write_text(content)
        report: dict[str, object] = {"open": run(root, args.output, restore=False)}
        child = subprocess.run(
            [
                sys.executable,
                __file__,
                "--restore",
                str(root),
                "--output",
                str(args.output),
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        report["restore"] = json.loads(child.stdout.strip().splitlines()[-1])
        assert source.read_text() == content
        report["source_preserved"] = True
        (args.output / "profiles.json").write_text(json.dumps(report, indent=2) + "\n")
        print(json.dumps(report))


if __name__ == "__main__":
    main()
