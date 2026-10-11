"""Native prepared browser search, selection, multi-open, retry and modal closure."""

import json
from pathlib import Path
from tempfile import TemporaryDirectory

import numpy as np
from imgui_bundle import hello_imgui
from PIL import Image
from rebuild_input import NativeInput, NativeText

from datelier.application.editor import EditorController
from datelier.gui.app import InspectionEvidence, run_gui
from datelier.gui.components.probe import GuiProbe


def main() -> None:
    with TemporaryDirectory(prefix="datelier-browser-") as directory:
        root = Path(directory)
        first, second = root / "needle##one.csv", root / "needle##two.csv"
        for path in (first, second):
            path.write_text("x,y\n1.0,2.0\n3.0,4.0\n")
        (root / "needle##alias.csv").symlink_to(first)
        for index in range(512):
            (root / f"unused-{index:04}.csv").write_text("metadata only")
        collection = root / "media"
        collection.mkdir()
        (collection / "original.txt").write_text("A complete original record.")
        Image.new("RGB", (12, 16), "red").save(collection / "original.png")
        original = tuple(path.read_bytes() for path in (first, second))
        native, text = NativeInput(), NativeText()
        stage = entered = 0
        done = False
        retained_source = ""

        def frame(
            editor: EditorController, probe: GuiProbe, evidence: InspectionEvidence
        ) -> None:
            nonlocal stage, entered, done, retained_source
            browser = editor.browser
            age = evidence.frames - entered
            if evidence.frames > 700:
                raise AssertionError(
                    (
                        stage,
                        browser.message,
                        [
                            (k.path, p)
                            for k, p in probe.targets.items()
                            if k.path[:1] == ("open",)
                        ],
                    )
                )
            if native.advance(evidence.frames) or text.advance(evidence.frames):
                return
            suffix: tuple[str, ...] | None = None
            if stage == 0 and evidence.frames > 12:
                browser.path = str(root)
                suffix = ("welcome", "files", "run")
            elif stage == 1 and browser.listing and not browser.busy:
                assert len(browser.listing.files) == 515
                rendered = [
                    k
                    for k in probe.targets
                    if "listing" in k.path and k.path[-1] == "select"
                ]
                assert 0 < len(rendered) < 25
                suffix = ("files", "search", "value")
            elif stage == 2:
                text.start("NEEDLE##", evidence.frames)
                stage, entered = 3, evidence.frames
            elif stage == 3 and age > 2:
                assert len(browser.shown) == 3
                suffix = ("files", "commands", "select-all", "run")
            elif stage == 4 and age > 3:
                assert browser.selected == {first, second}
                suffix = ("listing", "needle##one.csv", "select")
            elif stage == 5 and age > 3:
                assert browser.selected == {second}
                suffix = ("files", "commands", "select-all", "run")
            elif stage == 6 and age > 3:
                assert browser.selected == {first, second}
                suffix = ("files", "commands", "selected", "run")
            elif (
                stage == 7
                and not editor.opening.busy
                and len(editor.files) == 2
                and all(f.inspection for f in editor.files)
            ):
                assert not browser.busy and not browser.selected
                assert editor.source_paths == (first, second)
                editor.new_file()
                browser.path = str(root / "absent")
                stage, entered = 8, evidence.frames
            elif stage == 8:
                suffix = ("welcome", "files", "run")
            elif stage == 9 and not browser.busy and "retry" in browser.message:
                suffix = ("navigation", "folder", "value")
            elif stage == 10:
                text.start(str(collection), evidence.frames)
                stage, entered = 11, evidence.frames
            elif stage == 11:
                suffix = ("navigation", "commands", "browse", "run")
            elif stage == 12 and not browser.busy and browser.listing:
                assert browser.listing.directory == collection
                suffix = ("files", "commands", "collection", "run")
            elif stage == 13 and not editor.opening.busy and editor.current.inspection:
                assert editor.current.inspection.dataset.source.path == collection
                assert editor.current.inspection.dataset.table.height == 2
                retained_source = editor.active_id
                editor.new_file()
                stage, entered = 14, evidence.frames
            elif stage == 14:
                suffix = ("welcome", "files", "run")
            elif stage == 15 and not browser.busy:
                suffix = ("direct", "path", "value")
            elif stage == 16:
                text.start(str(second), evidence.frames)
                stage, entered = 17, evidence.frames
            elif stage == 17:
                suffix = ("direct", "commands", "submit", "run")
            elif stage == 18 and not editor.opening.busy and age > 4:
                assert (
                    editor.current.inspection
                    and editor.current.inspection.dataset.source.path == second
                )
                assert len(editor.files) == 4
                editor.activate(retained_source)
                editor.new_file()
                stage, entered = 19, evidence.frames
            elif stage == 19:
                suffix = ("welcome", "files", "run")
            elif stage == 20 and age > 3:
                suffix = ("open", "close-window")
            elif stage == 21 and age > 3:
                assert not browser.busy and not browser.selected
                assert not native.find(probe, ("open", "close-window"))
                assert browser.direct == str(second) and browser.search == "NEEDLE##"
                suffix = ("welcome", "files", "run")
            elif stage == 22 and not browser.busy and age > 4:
                assert native.find(probe, ("direct", "commands", "submit", "run"))
                assert tuple(path.read_bytes() for path in (first, second)) == original
                assert all(
                    not f.analysis.jobs.results and not f.analysis.jobs.busy
                    for f in editor.files
                )
                assert editor.playback.snapshot.request is None
                done = True
                hello_imgui.get_runner_params().app_shall_exit = True
            if suffix:
                point = native.find(probe, suffix)
                if point:
                    native.click_point(point, evidence.frames)
                    stage, entered = stage + 1, evidence.frames

        evidence = run_gui(on_probe_frame=frame)
        assert done
        screenshot = hello_imgui.final_app_window_screenshot()
        if screenshot is not None:
            Image.fromarray(screenshot).save("/tmp/datelier-rebuild-browser.png")
        report = {
            "frames": evidence.frames,
            "p95_ms": float(np.percentile(evidence.frame_intervals_ms, 95)),
            "virtualized_metadata_rows": 515,
            "native_literal_filename_search_and_alias_selection": True,
            "native_multi_open_and_direct_duplicate_focus": True,
            "native_failed_folder_retry_and_media_collection": True,
            "native_modal_close_and_retained_drafts": True,
            "source_preserved": True,
            "implicit_analysis": False,
            "implicit_playback": False,
        }
        Path("/tmp/datelier-rebuild-browser.json").write_text(
            json.dumps(report, indent=2)
        )
        print(json.dumps(report))


if __name__ == "__main__":
    main()
