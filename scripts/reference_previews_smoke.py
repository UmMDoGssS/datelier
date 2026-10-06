"""Native lazy thumbnails, scroll/switch and CPU/GPU lifetime acceptance."""

import hashlib
import json
from dataclasses import replace
from pathlib import Path
from tempfile import TemporaryDirectory

import numpy as np
from imgui_bundle import hello_imgui
from PIL import Image

from datelier.gui.app import InspectionEvidence, run_gui
from datelier.gui.editor_session import EditorSession
from datelier.gui.tabs import EditorTabs
from datelier.inspection.references.types import ReferenceMapping


def main() -> None:
    with TemporaryDirectory() as directory:
        root = Path(directory)
        data = root / "data"
        data.mkdir()
        images = root / "images"
        images.mkdir()
        other = root / "other"
        other.mkdir()
        for i in range(30):
            Image.new("RGB", (320, 160), (i * 8, 80, 150)).save(images / f"{i}.png")
        Image.new("RGB", (30, 20)).save(other / "0.png")
        (images / "note.txt").write_text("Native lazy text excerpt.\n" * 50)
        source = data / "records.csv"
        source.write_text(
            "id,image,text\n"
            + "".join(f"{i},{i % 30}.png,../images/note.txt\n" for i in range(300))
        )
        digest = hashlib.sha256(source.read_bytes()).hexdigest()
        stage = 0
        first_id = ""
        observed: dict[str, object] = {}

        def frame(
            editor: EditorSession, tabs: EditorTabs, evidence: InspectionEvidence
        ) -> None:
            nonlocal stage, first_id
            file = editor.active
            if (
                stage == 0
                and file.references.index is not None
                and file.reference_view.preview_frames
            ):
                first_id = file.identity
                resolution, _ = file.references.get("image", "0.png")
                if resolution is None:
                    return
                assert len(resolution.candidates) == 2 and resolution.asset is None
                file.references.configure(
                    replace(
                        file.references.settings,
                        mappings=(
                            ReferenceMapping("image", "0.png", str(images / "0.png")),
                        ),
                    )
                )
                file.reference_view.textures.invalidate()
                file.table.target_row = 151
                file.table.jump = True
                stage = 1
            elif (
                stage == 1
                and file.table.first_visible_row >= 140
                and file.reference_view.preview_frames > 25
            ):
                observed["scroll_thumbnails"] = True
                observed["gpu_bytes"] = file.reference_view.textures.retained_bytes
                observed["cpu_bytes"] = file.references.retained_bytes
                observed["rendered_rows"] = file.table.rendered_rows
                editor.new_tab(source)
                stage = 2
            elif (
                stage == 2
                and file.identity != first_id
                and file.loader.active
                and file.reference_view.preview_frames
            ):
                observed["independent_reference_jobs"] = True
                editor.close_tab(file.identity)
                editor.activate(first_id)
                stage = 3
            elif stage == 3 and file.reference_view.preview_frames > 40:
                observed["switch_reuse"] = True
                editor.close_tab(first_id)
                assert file.references.closed and not file.references.previews
                assert file.reference_view.textures.retained_bytes == 0
                observed["closed_cpu_gpu_bytes"] = 0
                hello_imgui.get_runner_params().app_shall_exit = True

        evidence = run_gui(source, smoke_frames=1500, on_editor_frame=frame)
        assert stage == 3 and observed.get("closed_cpu_gpu_bytes") == 0, (
            stage,
            observed,
        )
        assert hashlib.sha256(source.read_bytes()).hexdigest() == digest
        assert isinstance(observed["gpu_bytes"], int)
        assert observed["gpu_bytes"] <= 8 * 1048576
        assert isinstance(observed["cpu_bytes"], int)
        assert observed["cpu_bytes"] <= 16 * 1048576
        observed.update(
            frames=evidence.frames,
            frame_p95_ms=float(np.percentile(evidence.frame_intervals_ms, 95)),
            source_preserved=True,
        )
        print(json.dumps(observed))


if __name__ == "__main__":
    main()
