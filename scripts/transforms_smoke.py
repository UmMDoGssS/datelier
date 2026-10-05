"""Live typed-transform, diagnostic, history and prepared-schema checks."""

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
from datelier.pipeline.operations import Operation, describe_operation
from datelier.pipeline.types import (
    CastColumn,
    DerivedColumn,
    DropMissing,
    FillMissing,
    Lookup,
    TargetType,
    Unmatched,
)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output", type=Path, default=Path("/tmp/datelier-transforms.ppm")
    )
    args = parser.parse_args()
    actions: list[Operation | HistoryAction] = [
        CastColumn("v", TargetType.INT),
        CastColumn("v", TargetType.INT, False),
        FillMissing("v", 0),
        HistoryAction.UNDO,
        DropMissing(("v",)),
        Lookup(
            "label", (("a", "first"), ("c", "last")), TargetType.TEXT, Unmatched.ERROR
        ),
        DerivedColumn("score", 'col("v") * 2 + 1'),
        DerivedColumn("bad", '__import__("os").getcwd()'),
    ]
    expected = [
        (("1", "a"), ("bad", "b"), ("3", "c")),
        (("1", "a"), ("NULL", "b"), ("3", "c")),
        (("1", "a"), ("0", "b"), ("3", "c")),
        (("1", "a"), ("NULL", "b"), ("3", "c")),
        (("1", "a"), ("3", "c")),
        (("1", "first"), ("3", "last")),
        (("1", "first", "3"), ("3", "last", "7")),
        (("1", "first", "3"), ("3", "last", "7")),
    ]
    index, pending, completed = 0, False, 0
    observed: list[str] = []
    with TemporaryDirectory(prefix="datelier-transforms-") as directory:
        path = Path(directory) / "data.csv"
        path.write_text("v,label\n1,a\nbad,b\n3,c\n")
        original = path.read_bytes()

        def frame(session: GuiSession, evidence: InspectionEvidence) -> None:
            nonlocal index, pending, completed
            session.operations.column = "v"
            session.operations.transforms.expanded = False
            session.operations.derived_expanded = True
            session.operations.derived_name = "score"
            session.operations.expression = 'col("v") * 2 + 1'
            session.operations.transforms.dtype = 0
            if evidence.frames == 1:
                hello_imgui.get_runner_params().docking_params.focus_dockable_window(
                    "Transform and history"
                )
            active = session.loader.active
            if active is None or session.editor.busy or evidence.frames < 15:
                return
            if pending:
                assert active.first_page.rows == expected[index]
                assert active.first_page.row_ids == ((0, 1, 2) if index < 4 else (0, 2))
                assert session.pages.get(0) == active.first_page
                if index == 0:
                    assert "failed" in session.editor.message
                    assert (
                        session.editor.pipeline is not None
                        and not session.editor.pipeline.history
                    )
                elif index == 7:
                    assert "Unsupported" in session.editor.message
                    assert (
                        session.editor.pipeline is not None
                        and session.editor.pipeline.cursor == 4
                    )
                else:
                    assert active.schema[0].dtype == "Int64"
                action = actions[index]
                observed.append(
                    str(action)
                    if isinstance(action, HistoryAction)
                    else describe_operation(action)
                )
                index += 1
                pending = False
            if index < len(actions):
                session.editor.request(actions[index])
                pending = True
            elif not completed:
                completed = evidence.frames
            elif evidence.frames > completed + 45:
                hello_imgui.get_runner_params().app_shall_exit = True

        evidence = run_gui(path, smoke_frames=600, on_frame=frame)
        assert len(observed) == len(actions)
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
        print(
            f"Passed {len(observed)} live transform checks in {evidence.frames} frames"
        )


if __name__ == "__main__":
    main()
