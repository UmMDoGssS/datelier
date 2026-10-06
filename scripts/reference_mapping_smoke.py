"""Real native ambiguous-reference choice with a final thumbnail screenshot."""

import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from imgui_bundle import hello_imgui, imgui
from PIL import Image

from datelier.gui.app import GuiSession, InspectionEvidence, run_gui


def main() -> None:
    with TemporaryDirectory() as directory:
        root = Path(directory)
        for name in ("data", "red", "blue"):
            (root / name).mkdir()
        for name in ("red", "blue"):
            Image.new("RGB", (256, 128), name).save(root / name / "same.png")
        source = root / "data" / "records.csv"
        source.write_text(
            "image,note\nsame.png,ambiguous image\n"
            "../red/same.png,exact image\nmissing.png,missing image\n"
        )
        choose = target = (0.0, 0.0)
        original_button, original_select = imgui.small_button, imgui.selectable
        stage = entered = 0

        def button(label: str) -> bool:
            nonlocal choose
            result = original_button(label)
            if label == "Choose reference" and choose == (0.0, 0.0):
                lo, hi = imgui.get_item_rect_min(), imgui.get_item_rect_max()
                choose = ((lo.x + hi.x) / 2, (lo.y + hi.y) / 2)
            return result

        def select(
            label: str, selected: bool, flags: int = 0, size: imgui.ImVec2 | None = None
        ) -> tuple[bool, bool]:
            nonlocal target
            # The smoke wraps only the simple two-argument ambiguity choices.
            result = original_select(label, selected)
            if label == str(root / "red" / "same.png"):
                lo, hi = imgui.get_item_rect_min(), imgui.get_item_rect_max()
                target = ((lo.x + hi.x) / 2, (lo.y + hi.y) / 2)
            return result

        def frame(file: GuiSession, evidence: InspectionEvidence) -> None:
            nonlocal stage, entered
            io = imgui.get_io()
            age = evidence.frames - entered
            if stage == 0 and choose != (0.0, 0.0) and file.references.index:
                io.mouse_pos = imgui.ImVec2(*choose)
                io.want_set_mouse_pos = True
                stage, entered = 1, evidence.frames
            elif stage in (1, 4) and age > 3:
                io.add_mouse_button_event(0, True)
                stage, entered = stage + 1, evidence.frames
            elif stage in (2, 5) and age > 3:
                io.add_mouse_button_event(0, False)
                stage, entered = stage + 1, evidence.frames
            elif stage == 3 and target != (0.0, 0.0) and age > 5:
                io.mouse_pos = imgui.ImVec2(*target)
                io.want_set_mouse_pos = True
                stage, entered = 4, evidence.frames
            elif (
                stage == 6
                and file.references.settings.mappings
                and file.reference_view.preview_frames > 20
                and file.references.get("image", "same.png")[1] is not None
            ):
                mapping = file.references.settings.mappings[0]
                assert mapping.value == "same.png" and mapping.path == str(
                    root / "red" / "same.png"
                )
                hello_imgui.get_runner_params().app_shall_exit = True

        # Preserve the real selectable signature for table rows; only intercept
        # the known ambiguity path label, forwarding other calls unchanged.
        def dispatch(
            label: str, selected: bool, flags: int = 0, size: imgui.ImVec2 | None = None
        ) -> tuple[bool, bool]:
            if label == str(root / "red" / "same.png"):
                return select(label, selected)
            return original_select(label, selected, flags, size)

        with (
            patch.object(imgui, "small_button", side_effect=button),
            patch.object(imgui, "selectable", side_effect=dispatch),
        ):
            evidence = run_gui(source, smoke_frames=700, on_frame=frame)
        assert stage == 6, (stage, choose, target)
        pixels = hello_imgui.final_app_window_screenshot()
        Image.fromarray(pixels[:, :, :3]).save("/tmp/datelier-reference-mapping.png")
        print(
            json.dumps(
                {
                    "frames": evidence.frames,
                    "native_ambiguous_choice": True,
                    "screenshot": "/tmp/datelier-reference-mapping.png",
                }
            )
        )


if __name__ == "__main__":
    main()
