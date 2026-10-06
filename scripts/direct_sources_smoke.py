"""Native Open Folder collection action and independent explicit text-line import."""

import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from imgui_bundle import hello_imgui, imgui
from PIL import Image

from datelier.gui.app import InspectionEvidence, run_gui
from datelier.gui.editor_session import EditorSession
from datelier.gui.tabs import EditorTabs
from datelier.io.types import ImportFormat, MediaOptions


def main() -> None:
    with TemporaryDirectory() as directory:
        root = Path(directory) / "collection"
        root.mkdir()
        Image.new("RGB", (256, 128), "green").save(root / "image.png")
        text = root / "note.txt"
        text.write_text("first line\nsecond line\n")
        pixel = (0.0, 0.0)
        original = imgui.button
        stage = entered = 0
        collection_id = ""
        state: dict[str, object] = {}

        def button(label: str, size: imgui.ImVec2 | None = None) -> bool:
            nonlocal pixel
            result = original(label, size)
            if label == "Open folder as media collection":
                lo, hi = imgui.get_item_rect_min(), imgui.get_item_rect_max()
                pixel = ((lo.x + hi.x) / 2, (lo.y + hi.y) / 2)
            return result

        def frame(
            editor: EditorSession, tabs: EditorTabs, evidence: InspectionEvidence
        ) -> None:
            nonlocal stage, entered, collection_id
            state.update(
                phase=editor.active.loader.status.phase,
                message=editor.active.loader.status.message,
                browser=editor.browser.visible,
                path=str(editor.active.loader.status.path),
                previews=editor.active.reference_view.preview_frames,
                reference_message=editor.active.references.message,
            )
            io = imgui.get_io()
            age = evidence.frames - entered
            if stage == 0:
                editor.browser.path = str(root)
                editor.browser.open(editor.active_id, folder=True)
                stage, entered = 1, evidence.frames
            elif (
                stage == 1
                and age > 10
                and pixel != (0.0, 0.0)
                and not editor.browser.busy
            ):
                io.mouse_pos = imgui.ImVec2(*pixel)
                io.want_set_mouse_pos = True
                stage, entered = 2, evidence.frames
            elif stage == 2 and age > 3:
                io.add_mouse_button_event(0, True)
                stage, entered = 3, evidence.frames
            elif stage == 3 and age > 3:
                io.add_mouse_button_event(0, False)
                stage, entered = 4, evidence.frames
            elif stage == 4 and editor.active.reference_view.preview_frames > 10:
                file = editor.active
                assert (
                    file.loader.active
                    and file.loader.active.dataset.source.path == root
                )
                assert file.loader.active.row_count == 2
                assert (
                    file.references.index is not None
                    and not file.references.index.names
                )
                collection_id = file.identity
                blank = editor.new_tab()
                editor.opening.request(
                    (text,),
                    blank.identity,
                    format=ImportFormat.MEDIA,
                    options=MediaOptions(text_lines=True),
                )
                stage = 5
            elif (
                stage == 5
                and editor.active_id != collection_id
                and editor.active.loader.active
            ):
                file = editor.active
                assert file.loader.active is not None
                assert file.loader.active.dataset.table["text"].to_list() == [
                    "first line",
                    "second line",
                ]
                assert len(editor.files) == 2
                assert not file.analysis.jobs.results
                stage = 6
                hello_imgui.get_runner_params().app_shall_exit = True

        with patch.object(imgui, "button", side_effect=button):
            evidence = run_gui(smoke_frames=700, on_editor_frame=frame)
        assert stage == 6, (stage, pixel, state)
        print(
            json.dumps(
                {
                    "frames": evidence.frames,
                    "native_collection_open": True,
                    "explicit_text_lines": 2,
                    "metadata_records": 2,
                    "implicit_ml": 0,
                }
            )
        )


if __name__ == "__main__":
    main()
