"""Native wide-field gallery/detail controls and file-aligned record selection."""

import json
from dataclasses import replace
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

import polars as pl
from imgui_bundle import hello_imgui, imgui
from PIL import Image

from datelier.gui.app import InspectionEvidence, run_gui
from datelier.gui.editor_session import EditorSession
from datelier.gui.tabs import EditorTabs
from datelier.inspection.records.types import RecordMode
from datelier.pipeline.operations import Sort


def main() -> None:
    with TemporaryDirectory() as directory:
        root = Path(directory)
        (root / "data").mkdir()
        (root / "images").mkdir()
        for i in range(4):
            Image.new("RGB", (240, 120), (i * 50, 160, 80)).save(
                root / "images" / f"{i}.png"
            )
        paths = (root / "data" / "train.csv", root / "data" / "test.csv")
        data = pl.DataFrame(
            {
                "id": range(40),
                **{f"c{i}": [f"{i}-{r}" for r in range(40)] for i in range(40)},
                "image": [f"../images/{i % 4}.png" for i in range(40)],
            }
        )
        for path in paths:
            data.write_csv(path)
        pixels: dict[str, tuple[float, float]] = {}
        original_button, original_small = imgui.button, imgui.small_button
        stage = entered = 0
        first_id = ""
        focus_frame = -1
        state: dict[str, object] = {}

        def button(label: str, size: imgui.ImVec2 | None = None) -> bool:
            result = original_button(label, size)
            if label.startswith("Supporting fields") or label in (
                "All fields",
                "Next record",
                "Done",
            ):
                lo, hi = imgui.get_item_rect_min(), imgui.get_item_rect_max()
                pixels[
                    "Supporting fields"
                    if label.startswith("Supporting fields")
                    else label
                ] = ((lo.x + hi.x) / 2, (lo.y + hi.y) / 2)
            return result

        def small(label: str) -> bool:
            nonlocal focus_frame
            result = original_small(label)
            if label == "Focus record" and focus_frame != imgui.get_frame_count():
                lo, hi = imgui.get_item_rect_min(), imgui.get_item_rect_max()
                pixels[label] = ((lo.x + hi.x) / 2, (lo.y + hi.y) / 2)
                focus_frame = imgui.get_frame_count()
                state.update(
                    focus_hover=imgui.is_item_hovered(),
                    focus_clicked=bool(state.get("focus_clicked")) or result,
                )
            return result

        def frame(
            editor: EditorSession, tabs: EditorTabs, evidence: InspectionEvidence
        ) -> None:
            nonlocal stage, entered, first_id
            file = editor.active
            state.update(
                gallery=file.inspect.settings.gallery,
                focused=file.inspect.focused_row,
                cards=file.inspect.shown_cards,
                fields=len(file.inspect.settings.supporting or ()),
            )
            io = imgui.get_io()
            age = evidence.frames - entered
            if stage == 0:
                hello_imgui.get_runner_params().docking_params.focus_dockable_window(
                    "Inspect"
                )
                first_id = file.identity
                stage, entered = 1, evidence.frames
            elif stage == 1 and file.inspect.shown_cards > 10 and age > 20:
                io.mouse_pos = imgui.ImVec2(*pixels["Supporting fields"])
                io.want_set_mouse_pos = True
                stage, entered = 2, evidence.frames
            elif stage in (2, 5, 8, 11, 71) and age > 3:
                io.add_mouse_button_event(0, True)
                stage, entered = stage + 1, evidence.frames
            elif stage in (3, 6, 9, 12, 72) and age > 3:
                io.add_mouse_button_event(0, False)
                stage, entered = stage + 1, evidence.frames
            elif stage == 4 and "All fields" in pixels and age > 5:
                io.mouse_pos = imgui.ImVec2(*pixels["All fields"])
                io.want_set_mouse_pos = True
                stage, entered = 5, evidence.frames
            elif stage == 7 and len(file.inspect.settings.supporting or ()) == 42:
                io.mouse_pos = imgui.ImVec2(*pixels["Done"])
                io.want_set_mouse_pos = True
                stage, entered = 71, evidence.frames
            elif stage == 73 and age > 6:
                io.mouse_pos = imgui.ImVec2(*pixels["Focus record"])
                io.want_set_mouse_pos = True
                stage, entered = 8, evidence.frames
            elif (
                stage == 10
                and not file.inspect.settings.gallery
                and file.inspect.focused_row == 0
            ):
                page = file.inspect.jobs.get(0)
                assert page
                assert (
                    len(page.cards[0].fields) == 42
                    and page.cards[0].fields[40].text == "39-0"
                )
                io.mouse_pos = imgui.ImVec2(*pixels["Next record"])
                io.want_set_mouse_pos = True
                stage, entered = 11, evidence.frames
            elif stage == 13 and file.inspect.focused_row == 1:
                assert file.loader.active
                file.selection.choose(file.loader.active.dataset.revision, (1,))
                file.inspect.settings = replace(
                    file.inspect.settings, mode=RecordMode.SELECTION
                )
                stage = 14
            elif (
                stage == 14
                and file.inspect.jobs.active
                and file.inspect.jobs.active.row_ids.to_list() == [1]
            ):
                file.editor.request(Sort(("id",), True))
                stage = 15
            elif stage == 15 and not file.editor.busy:
                file.inspect.settings = replace(
                    file.inspect.settings,
                    mode=RecordMode.RANDOM,
                    count=5,
                    seed=17,
                    gallery=True,
                )
                stage = 16
            elif (
                stage == 16
                and file.inspect.jobs.active
                and len(file.inspect.jobs.active.row_ids) == 5
            ):
                page = file.inspect.jobs.get(0)
                if not page:
                    return
                card = page.cards[0]
                assert card.fields[40].text == f"39-{card.row_id}"
                assert card.position == 39 - card.row_id
                editor.new_tab(paths[1])
                stage = 17
            elif stage == 17 and file.identity != first_id and file.loader.active:
                file.selection.choose(file.loader.active.dataset.revision, (3,))
                file.inspect.settings = replace(
                    file.inspect.settings, mode=RecordMode.SELECTION
                )
                stage = 18
            elif (
                stage == 18
                and file.inspect.jobs.active
                and file.inspect.jobs.active.row_ids.to_list() == [3]
            ):
                editor.close_tab(file.identity)
                editor.activate(first_id)
                stage = 19
            elif stage == 19 and file.identity == first_id and file.inspect.jobs.active:
                assert (
                    file.inspect.settings.mode == RecordMode.RANDOM
                    and not file.selection.row_ids
                )
                assert file.inspect.rendered_cards < 10
                hello_imgui.get_runner_params().app_shall_exit = True

        with (
            patch.object(imgui, "button", side_effect=button),
            patch.object(imgui, "small_button", side_effect=small),
        ):
            evidence = run_gui(paths[0], smoke_frames=300, on_editor_frame=frame)
        Image.fromarray(hello_imgui.final_app_window_screenshot()[:, :, :3]).save(
            "/tmp/datelier-inspect-debug.png"
        )
        assert stage == 19, (stage, pixels, state)
        Image.fromarray(hello_imgui.final_app_window_screenshot()[:, :, :3]).save(
            "/tmp/datelier-inspect.png"
        )
        print(
            json.dumps(
                {
                    "frames": evidence.frames,
                    "native_all_42_fields": True,
                    "native_focus_next": True,
                    "sort_sample_alignment": True,
                    "cross_file_selection": True,
                    "screenshot": "/tmp/datelier-inspect.png",
                }
            )
        )


if __name__ == "__main__":
    main()
