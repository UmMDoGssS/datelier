"""Live transformed export/roundtrip and source-protection acceptance check."""

import argparse
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import cast

import numpy as np
import polars as pl
from imgui_bundle import hello_imgui
from numpy.typing import NDArray

from datelier.gui import GuiSession, InspectionEvidence, run_gui
from datelier.io.exporting import ExportFormat
from datelier.pipeline.operations import Sort
from datelier.pipeline.types import DerivedColumn


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("/tmp/datelier-export.ppm"))
    args = parser.parse_args()
    stage = 0
    completed = 0
    observed: list[str] = []
    with TemporaryDirectory(prefix="datelier-export-") as directory:
        root = Path(directory)
        path = root / "source.csv"
        path.write_text("v\n3\n1\n2\n")
        original = path.read_bytes()

        def frame(session: GuiSession, evidence: InspectionEvidence) -> None:
            nonlocal stage, completed
            if evidence.frames == 1:
                hello_imgui.get_runner_params().docking_params.focus_dockable_window(
                    "Export table"
                )
            active = session.loader.active
            if (
                active is None
                or session.editor.busy
                or session.exporter.busy
                or evidence.frames < 15
            ):
                return
            if stage == 0:
                session.editor.request(Sort(("v",)))
                stage = 1
            elif stage == 1:
                session.editor.request(DerivedColumn("double", 'col("v") * 2'))
                stage = 2
            elif stage == 2:
                session.exports.path = str(root / "result.csv")
                session.exporter.request(
                    active.dataset, root / "result.csv", ExportFormat.CSV
                )
                stage = 3
            elif stage == 3:
                assert session.exporter.result is not None
                assert session.exporter.result.revision == active.dataset.revision
                assert pl.read_csv(root / "result.csv").equals(active.dataset.table)
                observed.append("CSV roundtrip")
                session.exporter.request(
                    active.dataset, root / "result.parquet", ExportFormat.PARQUET
                )
                stage = 4
            elif stage == 4:
                assert pl.read_parquet(root / "result.parquet").equals(
                    active.dataset.table
                )
                observed.append("Parquet roundtrip")
                session.exports.path = str(path)
                session.exports.overwrite = True
                session.exporter.request(
                    active.dataset, path, ExportFormat.CSV, overwrite=True
                )
                stage = 5
            elif stage == 5:
                assert "source files are preserved" in session.exporter.message
                assert active.first_page.row_ids == (1, 2, 0)
                observed.append("Source replacement rejected")
                completed = evidence.frames
                stage = 6
            elif evidence.frames > completed + 45:
                hello_imgui.get_runner_params().app_shall_exit = True

        evidence = run_gui(path, smoke_frames=600, on_frame=frame)
        assert stage == 6 and path.read_bytes() == original
        pixels = cast(NDArray[np.uint8], hello_imgui.final_app_window_screenshot())
        height, width = pixels.shape[:2]
        args.output.write_bytes(
            f"P6\n{width} {height}\n255\n".encode() + pixels[:, :, :3].tobytes()
        )
        args.output.with_suffix(".json").write_text(
            json.dumps(
                {
                    "frames": evidence.frames,
                    "checks": observed,
                    "source_preserved": True,
                },
                indent=2,
            )
            + "\n"
        )
        print(f"Passed {len(observed)} live export checks in {evidence.frames} frames")


if __name__ == "__main__":
    main()
