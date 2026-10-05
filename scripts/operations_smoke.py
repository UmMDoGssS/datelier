"""Live history/preview gate on a Linux display with prepared-row assertions."""

import argparse
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import cast

import numpy as np
from imgui_bundle import hello_imgui
from numpy.typing import NDArray

from datelier.gui import GuiSession, InspectionEvidence, run_gui
from datelier.pipeline.editing import HistoryAction
from datelier.pipeline.operations import (
    Comparison,
    Filter,
    Operation,
    SelectColumns,
    Sort,
)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output", type=Path, default=Path("/tmp/datelier-operations.ppm")
    )
    args = parser.parse_args()
    actions: list[Operation | HistoryAction] = [
        Sort(("v",)),
        Filter("v", Comparison.LE, 2),
        SelectColumns(("label",)),
        HistoryAction.UNDO,
        HistoryAction.REDO,
        HistoryAction.UNDO,
        Filter("missing", Comparison.EQ, 1),
        SelectColumns(("v",)),
    ]
    expected_ids = [(1, 2, 0), (1, 2), (1, 2), (1, 2), (1, 2), (1, 2), (1, 2), (1, 2)]
    index = 0
    pending = False
    observed: list[str] = []
    revision = None
    completed_frame = 0
    with TemporaryDirectory(prefix="datelier-operations-") as directory:
        path = Path(directory) / "data.csv"
        path.write_text("v,label\n3,c\n1,a\n2,b\n")
        original = path.read_bytes()

        def frame(session: GuiSession, evidence: InspectionEvidence) -> None:
            nonlocal index, pending, revision, completed_frame
            if evidence.frames == 1:
                hello_imgui.get_runner_params().docking_params.focus_dockable_window(
                    "Transform and history"
                )
            active = session.loader.active
            if active is None or session.editor.busy or evidence.frames < 15:
                return
            if pending:
                assert active.first_page.row_ids == expected_ids[index]
                assert session.pages.get(0) == active.first_page
                assert session.table.prepared_visible_rows > 0
                if index == 6:
                    assert active.dataset.revision == revision
                    assert "failed" in session.editor.message
                    assert session.editor.pipeline is not None
                    assert session.editor.pipeline.can_redo
                else:
                    assert active.dataset.revision != revision
                observed.append(str(actions[index]))
                pending = False
                index += 1
            if index < len(actions):
                revision = active.dataset.revision
                session.editor.request(actions[index])
                pending = True
            elif not completed_frame:
                assert session.editor.pipeline is not None
                assert not session.editor.pipeline.can_redo
                assert active.first_page.rows == (("1",), ("2",))
                completed_frame = evidence.frames
            elif evidence.frames >= completed_frame + 45:
                hello_imgui.get_runner_params().app_shall_exit = True

        evidence = run_gui(path, smoke_frames=600, on_frame=frame)
        assert len(observed) == len(actions), observed
        assert evidence.table_dock_id and evidence.schema_dock_id
        assert path.read_bytes() == original
        pixels = cast(NDArray[np.uint8], hello_imgui.final_app_window_screenshot())
        height, width = pixels.shape[:2]
        args.output.write_bytes(
            f"P6\n{width} {height}\n255\n".encode() + pixels[:, :, :3].tobytes()
        )
        args.output.with_suffix(".json").write_text(
            json.dumps(
                {
                    "frames": evidence.frames,
                    "actions": observed,
                    "source_preserved": True,
                },
                indent=2,
            )
            + "\n"
        )
        print(f"Passed {len(observed)} live history checks in {evidence.frames} frames")


if __name__ == "__main__":
    main()
