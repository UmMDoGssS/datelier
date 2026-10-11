"""Native scoped image comparisons, resize, row links and original-pixel Inspect."""

import json
from dataclasses import replace
from pathlib import Path
from tempfile import TemporaryDirectory

import numpy as np
from imgui_bundle import hello_imgui, imgui
from PIL import Image
from rebuild_input import NativeInput

from datelier.application.comparisons import ComparisonFamily
from datelier.application.sessions import EditorController
from datelier.gui.app import InspectionEvidence, run_gui
from datelier.gui.components.probe import GuiProbe
from datelier.inspection.images.profiles import PixelScope
from datelier.pipeline import Sort


def main() -> None:
    with TemporaryDirectory(prefix="datelier-image-compare-") as directory:
        root = Path(directory)
        first = root / "train.csv"
        second = root / "test.csv"
        for name, width, red in (
            ("a2", 2, 10),
            ("a4", 4, 30),
            ("b6", 6, 50),
            ("b2", 2, 70),
        ):
            Image.new("RGB", (width, 2), (red, 20, 30)).save(root / f"{name}.png")
        first.write_text("image,label\na4.png,z\na2.png,a\n")
        second.write_text("picture\nb6.png\nb2.png\n")
        originals = first.read_bytes(), second.read_bytes()
        native = NativeInput()
        stage = entered = 0
        done = False
        first_id = ""

        def frame(
            editor: EditorController, probe: GuiProbe, evidence: InspectionEvidence
        ) -> None:
            nonlocal stage, entered, done, first_id
            model = editor.compare.images
            age = evidence.frames - entered
            if evidence.frames > 750:
                raise AssertionError(
                    (stage, model.message, model.jobs.selection_message)
                )
            if native.advance(evidence.frames):
                return
            suffix = None
            if stage == 0 and editor.active.inspection:
                first_id = editor.active_id
                editor.active.editor.request(Sort(("label",)))
                editor.new_file(second)
                stage, entered = 1, evidence.frames
            elif (
                stage == 1
                and len(editor.files) == 2
                and all(
                    f.inspection and not f.editor.busy and not f.references.busy
                    for f in editor.files
                )
            ):
                editor.choose_route("Compare files")
                editor.compare.tab = ComparisonFamily.IMAGES
                stage, entered = 2, evidence.frames
            elif stage == 2 and age > 5:
                suffix = ("contributors", "files", "open")
            elif stage == 3 and age > 5:
                suffix = ("files", "list", "bulk")
            elif stage == 4 and age > 5:
                assert len(model.draft.sources) == 2 and model.jobs.started == 0
                imgui.get_io().add_key_event(imgui.Key.escape, True)
                stage, entered = 5, evidence.frames
            elif stage == 5:
                imgui.get_io().add_key_event(imgui.Key.escape, False)
                model.draft = replace(
                    model.draft,
                    bins=2,
                    sources=tuple(
                        replace(
                            s,
                            profile=replace(
                                s.profile,
                                pixels=PixelScope.SAMPLE,
                                pixel_count=2,
                                pixel_seed=7,
                            ),
                        )
                        for s in model.draft.sources
                    ),
                )
                stage, entered = 6, evidence.frames
            elif stage == 6 and age > 5:
                suffix = ("recipe-controls", "apply", "run")
            elif stage == 7 and model.active and age > 5:
                assert [p.profiled_pixels for p in model.active.profiles] == [4, 4]
                assert editor.navigation.comparing and all(
                    f.images.profile_jobs.active is None for f in editor.all_files
                )
                suffix = ("image-dimension-viewport", "expand")
            elif stage == 8 and age > 5:
                suffix = ("image-dimension-viewport", "restore")
            elif stage == 9 and age > 5:
                suffix = ("Colors", "tab")
            elif stage == 10 and age > 5:
                if model.view.tab != "Colors":
                    if native.click(probe, ("Colors", "tab"), evidence.frames):
                        entered = evidence.frames
                    return
                assert model.color_groups == (("RGB", "|u1"),)
                suffix = ("image-color-viewport", "expand")
            elif stage == 11 and age > 5:
                suffix = ("image-color-viewport", "restore")
            elif stage == 12 and age > 5:
                suffix = ("Statistics", "tab")
            elif stage == 13 and age > 5:
                suffix = ("Dimensions", "tab")
            elif stage == 14 and age > 5:
                if model.view.tab != "Dimensions":
                    if native.click(probe, ("Dimensions", "tab"), evidence.frames):
                        entered = evidence.frames
                    return
                suffix = ("image-comparison-chart", "canvas")
            elif stage == 15 and editor.current.selection.row_ids:
                assert editor.active_id == first_id and not editor.navigation.comparing
                assert editor.current.selection.row_ids in ({0}, {1})
                editor.choose_route("Compare files")
                model.view = replace(model.view, source=0)
                stage, entered = 16, evidence.frames
            elif stage == 16 and age > 5:
                suffix = ("Records", "tab")
            elif stage == 17 and age > 5:
                suffix = ("records", "open-1")
            elif stage == 18 and editor.current.images.jobs.active:
                assert (
                    editor.current.views.tab == "Inspect"
                    and editor.current.selection.row_ids == {0}
                )
                assert editor.current.images.jobs.active.pixel(0, 0) == (30, 20, 30)
                assert originals == (first.read_bytes(), second.read_bytes())
                assert all(
                    not f.audio.player.snapshot.request for f in editor.all_files
                )
                done = True
                hello_imgui.get_runner_params().app_shall_exit = True
            if suffix and native.click(probe, suffix, evidence.frames):
                stage, entered = stage + 1, evidence.frames

        evidence = run_gui(initial_path=first, on_probe_frame=frame)
        assert done
        report = {
            "frames": evidence.frames,
            "p95_ms": float(np.percentile(evidence.frame_intervals_ms, 95)),
            "native_shared_contributors": True,
            "explicit_scoped_sampled_prepare": True,
            "compatible_color_groups": True,
            "dimensions_colors_statistics_records": True,
            "expand_restore_both_views": True,
            "original_sorted_rows_linked": True,
            "record_open_original_pixels": True,
            "source_preserved": True,
            "implicit_profiles_playback": False,
        }
        Path("/tmp/datelier-rebuild-image-comparisons.json").write_text(
            json.dumps(report, indent=2)
        )
        print(json.dumps(report))


if __name__ == "__main__":
    main()
