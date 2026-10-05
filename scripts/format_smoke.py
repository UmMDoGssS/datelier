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

from datelier.gui.app import GuiSession, InspectionEvidence, run_gui
from datelier.io.loading import LoadPhase
from datelier.io.types import ImportFormat, XmlOptions


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--format", choices=[str(f) for f in ImportFormat], required=True
    )
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--show-options", action="store_true")
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
        elif format == ImportFormat.XML:
            path.write_text(
                '<root xmlns="urn:smoke"><meta>excluded</meta><records>'
                "<record><id>1</id><value>1.5</value><label>café</label></record>"
                "<record><id>2</id><value/><label>last</label></record>"
                "</records></root>"
            )
            # Apply the exact settings exposed by the controls after startup.
        elif format == ImportFormat.PARQUET:
            table.write_parquet(path)
        else:
            table.write_ndjson(path)
        bad = root / ("bad." + format.lower())
        bad.write_text(
            "<root><record><payload><hidden>1</hidden></payload></record></root>"
            if format == ImportFormat.XML
            else 'a\n"unterminated\n'
            if format in (ImportFormat.CSV, ImportFormat.TSV)
            else '{"payload":{"hidden":1}}'
            if format == ImportFormat.JSONL
            else '[{"payload":{"hidden":1}}]'
        )
        original = path.read_bytes()
        expected = (("1", "1.5", "café"), ("2", "NULL", "last"))

        def frame(session: GuiSession, evidence: InspectionEvidence) -> None:
            if evidence.frames == 1:
                session.controls.options_expanded = True
            elif evidence.frames == 60 and not args.show_options:
                session.controls.options_expanded = False
            if format == ImportFormat.XML and evidence.frames == 1:
                session.controls.xml_path = "./s:records/s:record"
                session.controls.xml_namespaces = "s=urn:smoke"
                session.loader.request(path, session.controls.options(format))
                observed["extraction_controls"] = True
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
                if format == ImportFormat.XML:
                    session.loader.request(bad, XmlOptions(record_path="./record"))
                else:
                    session.loader.request(bad)
            if session.loader.status.phase == LoadPhase.FAILED:
                observed["failure_visible"] = True
                assert active is not None
                if format in (ImportFormat.JSON, ImportFormat.JSONL):
                    assert "nested JSON" in session.loader.status.message
                    observed["nested_diagnostic"] = True
                elif format == ImportFormat.XML:
                    assert "nested XML" in session.loader.status.message
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
