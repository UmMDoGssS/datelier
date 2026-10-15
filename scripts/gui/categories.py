"""Native grouped bars, box/violin/aggregate families and sorted category links."""

import json
from pathlib import Path
from tempfile import TemporaryDirectory

import numpy as np
from imgui_bundle import hello_imgui

from datelier.application.sessions import EditorController
from datelier.gui.app import InspectionEvidence, run_gui
from datelier.gui.components.probe import GuiProbe
from datelier.pipeline import Sort
from datelier.plotting.categories import CategoryRepresentation
from scripts.support.input import NativeInput


def main() -> None:
    with TemporaryDirectory(prefix="datelier-categories-") as directory:
        source = Path(directory) / "pairs.csv"
        source.write_text("kind,group,value\na,x,1.0\na,y,3.0\nb,x,2.0\nb,y,4.0\n")
        original = source.read_bytes()
        native = NativeInput()
        stage = entered = 0
        done = False

        def frame(
            editor: EditorController, probe: GuiProbe, evidence: InspectionEvidence
        ) -> None:
            nonlocal stage, entered, done
            file = editor.current
            data = file.explorer.active
            chart = data.category_chart if data else None
            age = evidence.frames - entered
            if evidence.frames > 550:
                raise AssertionError((stage, file.plots.error, file.explorer.message))
            if native.advance(evidence.frames):
                return
            suffix = None
            if stage == 0 and file.inspection and data:
                file.editor.request(Sort(("value",), True))
                stage, entered = 1, evidence.frames
            elif stage == 1 and not file.editor.busy and data:
                editor.choose_relationship_chart("Grouped count bars")
                stage, entered = 2, evidence.frames
            elif (
                stage == 2
                and chart
                and chart.settings.representation == CategoryRepresentation.GROUPED
                and age > 5
            ):
                suffix = ("bar-0-0",)
            elif stage == 3 and file.selection.row_ids:
                assert file.selection.row_ids == {0} and file.table.target_row == 4
                editor.choose_relationship_chart("Box")
                stage, entered = 4, evidence.frames
            elif (
                stage == 4
                and chart
                and chart.settings.representation == CategoryRepresentation.BOX
                and age > 5
            ):
                suffix = ("scatter", "expand")
            elif stage == 5 and age > 5:
                suffix = ("scatter", "restore")
            elif stage == 6 and age > 5:
                suffix = ("distribution-0",)
            elif stage == 7 and file.selection.row_ids == {0, 1}:
                assert file.table.target_row == 2
                editor.choose_relationship_chart("Violin")
                stage, entered = 8, evidence.frames
            elif (
                stage == 8
                and chart
                and chart.settings.representation == CategoryRepresentation.VIOLIN
                and age > 5
            ):
                assert len(chart.distributions[0].kde_x)
                suffix = ("distribution-1",)
            elif stage == 9 and file.selection.row_ids == {2, 3}:
                editor.choose_relationship_chart("Mean bars")
                stage, entered = 10, evidence.frames
            elif (
                stage == 10
                and chart
                and chart.settings.representation == CategoryRepresentation.MEAN
                and age > 5
            ):
                assert chart.values.tolist() == [[2, 3]]
                suffix = ("bar-0-0",)
            elif stage == 11 and file.selection.row_ids == {0, 1}:
                editor.choose_relationship_chart("Median bars")
                stage, entered = 12, evidence.frames
            elif (
                stage == 12
                and chart
                and chart.settings.representation == CategoryRepresentation.MEDIAN
                and age > 5
            ):
                editor.choose_relationship_chart("Sum bars")
                stage, entered = 13, evidence.frames
            elif (
                stage == 13
                and chart
                and chart.settings.representation == CategoryRepresentation.SUM
                and age > 5
            ):
                assert chart.values.tolist() == [[4, 6]]
                editor.choose_relationship_chart("Count bars")
                stage, entered = 14, evidence.frames
            elif stage == 14 and age > 5:
                assert file.views.tab == "Profiles" and file.profiles.selected == (
                    "kind",
                )
                assert (
                    source.read_bytes() == original and not file.analysis.jobs.results
                )
                done = True
                hello_imgui.get_runner_params().app_shall_exit = True
            if suffix and native.click(probe, suffix, evidence.frames):
                stage, entered = stage + 1, evidence.frames

        evidence = run_gui(initial_path=source, on_probe_frame=frame)
        assert done
        report = {
            "frames": evidence.frames,
            "p95_ms": float(np.percentile(evidence.frame_intervals_ms, 95)),
            "native_grouped_box_violin_aggregates": True,
            "category_original_sorted_rows": True,
            "native_expand_restore": True,
            "counts_route_to_profiles": True,
            "source_preserved": True,
            "implicit_analysis": False,
        }
        Path("/tmp/datelier-rebuild-categories.json").write_text(
            json.dumps(report, indent=2)
        )
        print(json.dumps(report))


if __name__ == "__main__":
    main()
