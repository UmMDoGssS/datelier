"""Native source/member navigation and explicit slice/record reconstruction."""

import json
from importlib import import_module
from pathlib import Path
from tempfile import TemporaryDirectory

import numpy as np
from imgui_bundle import hello_imgui
from rebuild_input import NativeInput

from datelier.application.sessions import EditorController
from datelier.gui.app import InspectionEvidence, run_gui
from datelier.gui.components.probe import GuiProbe
from datelier.io.types import ImportFormat, ObjectOptions


def main() -> None:
    with TemporaryDirectory(prefix="datelier-rebuild-sources-") as directory:
        root = Path(directory)
        arrays, structured = root / "arrays.npz", root / "object.json"
        values = np.arange(60).reshape(3, 4, 5)
        np.savez_compressed(arrays, cube=values, wrong=np.arange(2))
        structured.write_text('{"rows":[{"x":3,"name":"中"},{"x":1,"name":"second"}]}')
        checkpoint = root / "weights.pt"
        torch = import_module("torch")
        torch.save({"weight": torch.arange(24).reshape(2, 3, 4)}, checkpoint)
        originals = {
            path: path.read_bytes() for path in (arrays, structured, checkpoint)
        }
        stage, entered, next_stage = 0, 0, 0
        native = NativeInput()
        done = False

        def frame(
            editor: EditorController, probe: GuiProbe, evidence: InspectionEvidence
        ) -> None:
            nonlocal stage, entered, next_stage, done
            file = editor.current
            age = evidence.frames - entered
            if evidence.frames > 600:
                raise AssertionError(
                    (stage, file.arrays.message, file.record_views.message)
                )
            if native.advance(evidence.frames):
                return
            suffix: tuple[str, ...] | None = None
            if stage == 0 and file.arrays.catalog and age > 5:
                assert (
                    file.arrays.active is None
                    and file.arrays.store.temporary_path is None
                )
                suffix, next_stage = ("members", "cube", "select"), 1
            elif stage == 1 and age > 5:
                assert file.views.tab == "Inspect" and file.array_source.member_mode
                assert file.arrays.active is None
                suffix, next_stage = ("slice-settings", "prepare", "run"), 2
            elif stage == 2 and file.arrays.active:
                np.testing.assert_array_equal(file.arrays.active.raw, values[0])
                assert file.arrays.active.raw.flags.writeable is False
                new = editor.new_file()
                new.open(structured, ObjectOptions(), format=ImportFormat.OBJECT)
                stage, entered = 3, evidence.frames
            elif stage == 3 and file.objects.root and age > 5:
                suffix, next_stage = ("entries", repr(("rows",)), "open"), 4
            elif stage == 4 and age > 5:
                assert file.record_views.path == ("rows",)
                suffix, next_stage = ("objects", "records", "run"), 5
            elif stage == 5 and editor.current is not editor.active and file.inspection:
                assert file.inspection.dataset.table["x"].to_list() == [3, 1]
                assert file.inspection.dataset.row_ids.to_list() == [0, 1]
                editor.new_file(checkpoint)
                stage, entered = 6, evidence.frames
            elif stage == 6 and file.checkpoints.catalog and age > 5:
                assert (
                    file.checkpoints.active is None
                    and file.checkpoints.store.loads == 0
                )
                suffix, next_stage = ("members", "$['weight']", "select"), 7
            elif stage == 7 and age > 5:
                suffix, next_stage = ("slice-settings", "prepare", "run"), 8
            elif stage == 8 and file.checkpoints.active:
                np.testing.assert_array_equal(
                    file.checkpoints.active.view.raw, np.arange(24).reshape(2, 3, 4)[0]
                )
                assert all(
                    path.read_bytes() == data for path, data in originals.items()
                )
                assert all(
                    f.text.jobs.profile is None and f.images.profile_jobs.active is None
                    for f in editor.all_files
                )
                assert not editor.playback.snapshot.request
                done = True
                hello_imgui.get_runner_params().app_shall_exit = True
            if suffix:
                point = next(
                    (
                        value
                        for key, value in probe.targets.items()
                        if key.path[-len(suffix) :] == suffix
                    ),
                    None,
                )
                if point:
                    assert 0 <= point[1] < 800, (suffix, point)
                    native.click_point(point, evidence.frames)
                    stage, entered = next_stage, evidence.frames

        evidence = run_gui(initial_path=arrays, on_probe_frame=frame)
        assert done
        report = {
            "frames": evidence.frames,
            "p95_ms": float(np.percentile(evidence.frame_intervals_ms, 95)),
            "native_member_slice": True,
            "native_object_records": True,
            "native_checkpoint_slice": True,
            "source_row_identity": True,
            "source_preserved": True,
            "implicit_collection_playback": 0,
        }
        Path("/tmp/datelier-rebuild-sources.json").write_text(
            json.dumps(report, indent=2)
        )
        print(json.dumps(report))


if __name__ == "__main__":
    main()
