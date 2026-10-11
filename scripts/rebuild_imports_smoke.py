"""Native import validation, typed forms, transactional failure and successful retry."""

import json
from pathlib import Path
from tempfile import TemporaryDirectory

import numpy as np
from imgui_bundle import hello_imgui
from rebuild_input import NativeInput, NativeText

from datelier.application.editor import EditorController
from datelier.gui.app import InspectionEvidence, run_gui
from datelier.gui.components.probe import GuiProbe
from datelier.io.loading import LoadPhase
from datelier.io.types import CsvOptions, ImportFormat
from datelier.pipeline.operations import Sort


def main() -> None:
    with TemporaryDirectory(prefix="datelier-imports-") as directory:
        source, missing = (
            Path(directory) / "numbers.csv",
            Path(directory) / "missing.csv",
        )
        source.write_text("x;y\n1.0;NA\n3.0;30.0\n2.0;20.0\n")
        original = source.read_bytes()
        native, text = NativeInput(), NativeText()
        stage = entered = generation = 0
        done = False
        forms = {
            ImportFormat.CSV: ("delimited", "separator", "value"),
            ImportFormat.TSV: ("delimited", "separator", "value"),
            ImportFormat.JSON: ("json", "text", "value"),
            ImportFormat.JSONL: ("json", "text", "value"),
            ImportFormat.PARQUET: ("parquet", "columns", "value"),
            ImportFormat.XML: ("xml", "record", "value"),
            ImportFormat.MEDIA: ("media", "lines", "value"),
            ImportFormat.OBJECT: ("object", "syntax", "value"),
            ImportFormat.ARRAY: ("array", "container", "value"),
            ImportFormat.CHECKPOINT: ("checkpoint", "depth", "value"),
        }
        remaining = list(forms)

        def frame(
            editor: EditorController, probe: GuiProbe, evidence: InspectionEvidence
        ) -> None:
            nonlocal stage, entered, generation, done
            file = editor.current
            age = evidence.frames - entered
            if evidence.frames > 1600:
                raise AssertionError(
                    (
                        stage,
                        file.loader.status,
                        [
                            (k.path, p)
                            for k, p in probe.targets.items()
                            if "import-settings" in k.path
                        ],
                    )
                )
            if native.advance(evidence.frames) or text.advance(evidence.frames):
                return
            suffix = None
            if stage == 0 and file.inspection and file.explorer.active:
                assert file.inspection.dataset.table.columns == ["x;y"]
                generation = file.loader.generation
                suffix = ("import-settings", "toggle")
            elif stage == 1:
                suffix = ("delimited", "separator", "value")
            elif stage == 2:
                text.start("::", evidence.frames)
                stage, entered = 3, evidence.frames
            elif stage == 3:
                suffix = ("import-settings", "import", "run")
            elif stage == 4 and age > 4:
                assert (
                    file.imports.csv.separator == "::"
                    and file.loader.generation == generation
                )
                suffix = ("delimited", "separator", "value")
            elif stage == 5:
                text.start(";", evidence.frames)
                stage, entered = 6, evidence.frames
            elif stage == 6:
                suffix = ("delimited", "nulls", "value")
            elif stage == 7:
                text.start("NA", evidence.frames)
                stage, entered = 8, evidence.frames
            elif stage == 8:
                suffix = ("import-settings", "import", "run")
            elif stage == 9 and not file.imports.busy and file.inspection:
                assert file.inspection.dataset.table.columns == ["x", "y"], (
                    file.loader.status
                )
                assert file.inspection.dataset.table["y"].null_count() == 1
                assert isinstance(file.inspection.imported.options, CsvOptions)
                assert file.inspection.imported.options.null_values == ("NA",)
                file.editor.request(Sort(("x",), True))
                stage, entered = 10, evidence.frames
            elif stage == 10 and not file.editor.busy:
                assert (
                    file.inspection
                    and file.inspection.dataset.row_ids.to_list() == [1, 2, 0]
                )
                suffix = ("import-settings", "path", "value")
            elif stage == 11:
                text.start(str(missing), evidence.frames)
                stage, entered = 12, evidence.frames
            elif stage == 12:
                suffix = ("import-settings", "import", "run")
            elif stage == 13 and not file.imports.busy:
                assert file.loader.status.phase == LoadPhase.FAILED
                assert (
                    file.inspection
                    and file.inspection.dataset.row_ids.to_list() == [1, 2, 0]
                )
                suffix = ("import-settings", "path", "value")
            elif stage == 14:
                text.start(str(source), evidence.frames)
                stage, entered = 15, evidence.frames
            elif stage == 15:
                suffix = ("import-settings", "import", "run")
            elif stage == 16 and not file.imports.busy and age > 5:
                assert file.loader.status.phase == LoadPhase.READY
                assert (
                    file.inspection
                    and file.inspection.dataset.row_ids.to_list() == [0, 1, 2]
                )
                generation = file.loader.generation
                stage, entered = 17, evidence.frames
            elif stage == 17 and age > 2:
                if remaining:
                    file.imports.format = remaining.pop(0)
                    stage, entered = 18, evidence.frames
                else:
                    assert (
                        file.loader.generation == generation
                        and not file.analysis.jobs.results
                    )
                    assert source.read_bytes() == original
                    done = True
                    hello_imgui.get_runner_params().app_shall_exit = True
            elif stage == 18 and age > 2:
                assert file.imports.format
                assert native.find(probe, forms[file.imports.format]) is not None
                stage, entered = 17, evidence.frames
            if suffix and native.click(probe, suffix, evidence.frames):
                stage, entered = stage + 1, evidence.frames

        evidence = run_gui(initial_path=source, on_probe_frame=frame)
        assert done
        report = {
            "frames": evidence.frames,
            "p95_ms": float(np.percentile(evidence.frame_intervals_ms, 95)),
            "native_delimiter_and_null_token_edits": True,
            "native_invalid_draft_never_requests_load": True,
            "native_failed_reload_preserves_pipeline": True,
            "native_successful_retry_replaces_pipeline": True,
            "ten_format_forms_render_without_loading": True,
            "source_preserved": True,
            "implicit_analysis": False,
        }
        Path("/tmp/datelier-rebuild-imports.json").write_text(
            json.dumps(report, indent=2)
        )
        print(json.dumps(report))


if __name__ == "__main__":
    main()
