"""Native explicit image collection, subtabs, shared sizing and result opening."""

import json
from dataclasses import replace
from pathlib import Path
from tempfile import TemporaryDirectory

import numpy as np
from imgui_bundle import hello_imgui
from PIL import Image
from rebuild_input import NativeInput

from datelier.application.sessions import EditorController
from datelier.gui.app import InspectionEvidence, run_gui
from datelier.gui.components.probe import GuiProbe
from datelier.inspection.images.profiles import PixelScope


def main() -> None:
    with TemporaryDirectory(prefix="datelier-rebuild-images-") as directory:
        root = Path(directory)
        source = root / "images.csv"
        Image.new("RGB", (64, 32), (12, 24, 36)).save(root / "a.png")
        Image.new("RGB", (16, 32), (24, 48, 72)).save(root / "b.png")
        source.write_text("image,label\na.png,a\nb.png,b\nmissing.png,missing\n")
        original = source.read_bytes()
        inputs, stage, entered, done = NativeInput(), 0, 0, False

        def frame(
            editor: EditorController, probe: GuiProbe, evidence: InspectionEvidence
        ) -> None:
            nonlocal stage, entered, done
            file = editor.current
            age = evidence.frames - entered
            if evidence.frames > 650:
                raise AssertionError(
                    (stage, file.images.profile_jobs.message, file.images.jobs.message)
                )
            if inputs.advance(evidence.frames):
                return
            suffix: tuple[str, ...] | None = None
            if stage == 0 and file.inspection and not file.references.busy:
                file.profiles.choose(("image",))
                editor.choose_route("Profiles")
                assert (
                    file.images.profile_jobs.active is None
                    and not file.images.profile_jobs.busy
                )
                file.images.settings = replace(
                    file.images.settings,
                    profile=replace(
                        file.images.settings.profile,
                        pixels=PixelScope.SAMPLE,
                        pixel_count=200,
                        pixel_seed=7,
                    ),
                )
                stage, entered = 1, evidence.frames
            elif stage == 1 and age > 6:
                suffix = ("image-profile-settings", "prepare", "run")
            elif stage == 2 and file.images.profile_jobs.active:
                profile = file.images.profile_jobs.active
                assert (
                    profile.ready == 2
                    and profile.unresolved == 1
                    and profile.profiled_pixels == 400
                )
                assert file.images.jobs.metadata is None
                suffix = ("Dimensions", "tab")
            elif stage == 3 and age > 5:
                assert file.images.settings.profile_view.tab == "Dimensions"
                suffix = ("dimensions", "expand")
            elif stage == 4 and age > 5:
                suffix = ("dimensions", "restore")
            elif stage == 5 and age > 5:
                suffix = ("Colors", "tab")
            elif stage == 6 and age > 5:
                assert file.images.settings.profile_view.tab == "Colors"
                suffix = ("Record outcomes", "tab")
            elif stage == 7 and age > 5:
                suffix = ("record-outcomes", "open-1")
            elif stage == 8 and file.images.jobs.active:
                assert file.views.tab == "Inspect" and file.selection.row_ids == {1}
                assert file.images.jobs.active.pixel(0, 0) == (24, 48, 72)
                assert not file.records.settings.gallery and file.table.target_row == 2
                suffix = ("image-settings", "range", "toggle")
            elif stage == 9 and age > 5:
                suffix = ("display-range", "apply", "run")
            elif stage == 10 and age > 5:
                assert source.read_bytes() == original
                assert not file.audio.player.snapshot.request
                done = True
                hello_imgui.get_runner_params().app_shall_exit = True
            if suffix and inputs.click(probe, suffix, evidence.frames):
                stage, entered = stage + 1, evidence.frames

        evidence = run_gui(initial_path=source, on_probe_frame=frame)
        assert done
        report = {
            "frames": evidence.frames,
            "p95_ms": float(np.percentile(evidence.frame_intervals_ms, 95)),
            "native_explicit_sampled_profile": True,
            "native_dimensions_colors_outcomes": True,
            "native_expand_restore": True,
            "native_profile_record_open": True,
            "original_pixel_values": True,
            "source_preserved": True,
            "implicit_collection_or_playback": False,
        }
        Path("/tmp/datelier-rebuild-image-profiles.json").write_text(
            json.dumps(report, indent=2)
        )
        print(json.dumps(report))


if __name__ == "__main__":
    main()
