"""Native typed-cell shading, selected rows, scales and light/dark verification."""

import argparse
import json
from pathlib import Path
from tempfile import TemporaryDirectory

import polars as pl
from imgui_bundle import hello_imgui, imgui
from PIL import Image

from datelier.gui.app import GuiSession, InspectionEvidence, run_gui
from datelier.inspection.presentation import NumericScale, TablePresentation, cell_style
from datelier.pipeline.editing import HistoryAction
from datelier.pipeline.operations import Sort
from datelier.workspace.preferences import Theme


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--theme", choices=("light", "dark"), default="dark")
    args = parser.parse_args()
    with TemporaryDirectory() as directory:
        source = Path(directory) / "styles.parquet"
        pl.DataFrame(
            {
                "id": range(8),
                "value": [0.0, 1.0, 2.0, 3.0, 4.0, 100.0, float("inf"), None],
                "constant": [5.0] * 8,
                "category": ["a", "b", "a", None, "NULL", "b", "a", "a"],
            }
        ).write_parquet(source)
        stage = entered = 0

        def frame(file: GuiSession, evidence: InspectionEvidence) -> None:
            nonlocal stage, entered
            if file.loader.active is None:
                return
            age = evidence.frames - entered
            io = imgui.get_io()
            if stage == 0 and file.table.first_row_id is not None:
                file.preferences.apply_theme(
                    Theme.LIGHT if args.theme == "light" else Theme.DARK
                )
                io.mouse_pos = imgui.ImVec2(*file.table.first_row_pixel)
                io.want_set_mouse_pos = True
                stage, entered = 1, evidence.frames
            elif stage == 1 and age > 3:
                io.add_mouse_button_event(0, True)
                stage, entered = 2, evidence.frames
            elif stage == 2 and age > 3:
                io.add_mouse_button_event(0, False)
                stage, entered = 3, evidence.frames
            elif stage == 3 and file.table.selected_visible_rows:
                assert file.selection.row_ids == {0}
                page = file.pages.get(0)
                assert page
                cells = page.cells
                assert cells[3][3].is_null and not cells[4][3].is_null
                bounds = next(
                    b for b in file.loader.active.bounds if b.column == "value"
                )
                assert (
                    cell_style(
                        cells[5][1], bounds, file.table.presentation.settings
                    ).marker
                    == ">"
                )
                file.table.presentation.settings = TablePresentation(
                    scale=NumericScale.LINEAR
                )
                file.editor.request(Sort(("value",), True))
                stage, entered = 4, evidence.frames
            elif stage == 4 and not file.editor.busy:
                assert file.loader.active.first_page.row_ids != tuple(range(8))
                file.editor.request(HistoryAction.UNDO)
                stage, entered = 5, evidence.frames
            elif stage == 5 and not file.editor.busy:
                assert file.loader.active.first_page.row_ids == tuple(range(8))
                file.table.presentation.settings = TablePresentation(
                    scale=NumericScale.CUSTOM, minimum=1, maximum=4
                )
                file.selection.choose(file.loader.active.dataset.revision, (4,))
                file.table.column_start = 1
                file.table.target_row = 5
                file.table.jump = True
                stage, entered = 6, evidence.frames
            elif stage == 6 and age > 20:
                assert file.table.selected_visible_rows == 1
                assert file.table.rendered_rows < 20
                hello_imgui.get_runner_params().app_shall_exit = True

        evidence = run_gui(source, smoke_frames=600, on_frame=frame)
        assert stage == 6
        path = f"/tmp/datelier-table-styles-{args.theme}.png"
        Image.fromarray(hello_imgui.final_app_window_screenshot()[:, :, :3]).save(path)
        print(
            json.dumps(
                {
                    "theme": args.theme,
                    "frames": evidence.frames,
                    "native_selection": True,
                    "scales": 3,
                    "sort_undo": True,
                    "screenshot": path,
                }
            )
        )


if __name__ == "__main__":
    main()
