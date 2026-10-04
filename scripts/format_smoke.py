"""Per-format import, prepared preview, and diagnostic GUI acceptance checks."""

import argparse
import json
from dataclasses import asdict
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import cast

import numpy as np
import polars as pl
from imgui_bundle import hello_imgui
from numpy.typing import NDArray

from datelier.gui import GuiSession, InspectionEvidence, run_gui
from datelier.import_types import ImportFormat
from datelier.loading import LoadPhase


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--format", choices=[str(f) for f in ImportFormat], required=True
    )
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    format = ImportFormat(args.format)
    observed: dict[str, bool | int] = {}
    with TemporaryDirectory(prefix="datelier-format-") as directory:
        root = Path(directory)
        path = root / ("fixture." + format.lower())
        table = pl.DataFrame(
            {"id": [1, 2], "value": [1.5, None], "label": ["café", "last"]}
        )
        if format in (ImportFormat.CSV, ImportFormat.TSV):
            table.write_csv(path, separator="\t" if format == ImportFormat.TSV else ",")
        elif format == ImportFormat.JSON:
            table.write_json(path)
        elif format == ImportFormat.PARQUET:
            table.write_parquet(path)
        else:
            table.write_ndjson(path)
        bad = root / ("bad." + format.lower())
        bad.write_text(
            '{"payload":{"hidden":1}}'
            if format == ImportFormat.JSONL
            else '[{"payload":{"hidden":1}}]'
        )
        original = path.read_bytes()
        expected = (("1", "1.5", "café"), ("2", "NULL", "last"))

        def frame(session: GuiSession, evidence: InspectionEvidence) -> None:
            active = session.loader.active
            if active:
                assert active.imported.format == format
                assert active.dataset.table.rows() == table.rows()
                assert active.first_page.rows == expected
                assert active.first_page.row_ids == (0, 1)
                assert active.schema[1].null_count == 1
                if session.table.prepared_visible_rows:
                    observed["prepared_preview"] = True
            if evidence.frames == 30:
                session.loader.request(bad)
            if session.loader.status.phase == LoadPhase.FAILED:
                observed["failure_visible"] = True
                assert active is not None
                if format in (ImportFormat.JSON, ImportFormat.JSONL):
                    assert "nested JSON" in session.loader.status.message
                    observed["nested_diagnostic"] = True

        evidence = run_gui(path, smoke_frames=90, on_frame=frame)
        assert observed.get("prepared_preview") and observed.get("failure_visible")
        assert evidence.table_dock_id and evidence.schema_dock_id
        assert path.read_bytes() == original
        pixels = cast(NDArray[np.uint8], hello_imgui.final_app_window_screenshot())
        height, width = pixels.shape[:2]
        args.output.write_bytes(
            f"P6\n{width} {height}\n255\n".encode() + pixels[:, :, :3].tobytes()
        )
        report = {"format": str(format), **asdict(evidence), "observed": observed}
        args.output.with_suffix(".json").write_text(json.dumps(report, indent=2) + "\n")
        print(
            json.dumps(
                {"format": str(format), "frames": evidence.frames, "observed": observed}
            )
        )


if __name__ == "__main__":
    main()
