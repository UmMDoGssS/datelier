"""Native array gallery sampling, bounded GPU ownership and sorted exact opening."""

import json
from dataclasses import replace
from pathlib import Path
from tempfile import TemporaryDirectory
from time import perf_counter

import numpy as np
from imgui_bundle import hello_imgui
from rebuild_input import NativeInput

from datelier.application.sessions import EditorController
from datelier.gui.app import InspectionEvidence, run_gui
from datelier.gui.components.probe import GuiProbe
from datelier.pipeline.operations import Sort


def main() -> None:
    with TemporaryDirectory(prefix="datelier-gallery-") as directory:
        source = Path(directory) / "pictures.npz"
        pixels = np.stack(
            [np.full((257, 513), row * 30, dtype=np.uint8) for row in range(8)]
        )
        np.savez_compressed(source, pixels=pixels, priority=np.arange(8)[::-1])
        original = source.read_bytes()
        native = NativeInput()
        stage = entered = 0
        done = False
        max_bytes = max_uploads = max_pending = 0
        first_preview_ms = 0.0
        requested_at = 0.0

        def frame(
            editor: EditorController, probe: GuiProbe, evidence: InspectionEvidence
        ) -> None:
            nonlocal \
                stage, \
                entered, \
                done, \
                max_bytes, \
                max_uploads, \
                max_pending, \
                first_preview_ms
            nonlocal requested_at
            file = editor.current
            age = evidence.frames - entered
            if evidence.frames > 700:
                raise AssertionError(
                    (stage, file.gallery.errors, [key.path for key in probe.targets])
                )
            # The page owns the cache; expose only resource measurements to this gate.
            gpu = next(
                (
                    value
                    for key, value in probe.measurements.items()
                    if key.path[-1:] == ("preview-cache",)
                ),
                (0, 0),
            )
            max_bytes, max_uploads = (
                max(max_bytes, int(gpu[0])),
                max(max_uploads, int(gpu[1])),
            )
            max_pending = max(max_pending, file.gallery.pending)
            if native.advance(evidence.frames):
                return
            suffix: tuple[str, ...] | None = None
            if stage == 0 and file.inspection:
                assert file.gallery.pending == 0 and not file.gallery.previews
                file.references.configure(
                    replace(
                        file.references.settings,
                        cpu_bytes=1024 * 1024,
                        gpu_bytes=1024 * 1024,
                    )
                )
                file.images.settings = replace(
                    file.images.settings,
                    display=replace(file.images.settings.display, value_range=(0, 210)),
                )
                file.records.settings = replace(
                    file.records.settings, primary="pixels", count=8, gallery=True
                )
                editor.choose_route("Inspect")
                stage, entered = 1, evidence.frames
                requested_at = perf_counter()
            elif stage == 1:
                shown = [
                    (key, value)
                    for key, value in probe.measurements.items()
                    if key.path[-2:] == ("array-preview", "shown") and value[0] == 1
                ]
                if shown:
                    first_preview_ms = (perf_counter() - requested_at) * 1000
                    assert first_preview_ms <= 2000, first_preview_ms
                    assert all(
                        value.step == 5 for value in file.gallery.previews.values()
                    )
                    assert file.references.source is None
                    file.editor.request(Sort(("priority",)))
                    stage, entered = 2, evidence.frames
            elif stage == 2 and not file.editor.busy and age > 4:
                assert file.inspection and file.inspection.dataset.row_ids[0] == 7
                suffix = ("records", "7", "header", "open")
            elif stage == 3 and age > 3 and file.images.jobs.active:
                result = file.images.jobs.active
                assert result.locator.origin.row_id == 7
                assert result.pixel(0, 0) == (210,)
                assert not file.records.settings.gallery
                file.records.settings = replace(file.records.settings, gallery=True)
                stage, entered = 4, evidence.frames
            elif stage == 4 and age > 15:
                assert (
                    file.gallery.retained_bytes + file.references.retained_bytes
                    <= 1024 * 1024
                )
                assert 0 < max_bytes <= 1024 * 1024
                assert 0 < max_uploads <= 4 and 0 < max_pending <= 2
                assert (
                    source.read_bytes() == original and not file.analysis.jobs.results
                )
                assert (
                    file.images.profile_jobs.active is None
                    and not editor.playback.snapshot.request
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
            "first_visible_preview_ms": first_preview_ms,
            "max_shared_gpu_bytes": max_bytes,
            "max_shared_uploads_per_frame": max_uploads,
            "max_pending_array_previews": max_pending,
            "native_sorted_gallery_open_exact_pixels": True,
            "visible_only_no_collection_analysis": True,
            "source_preserved": True,
        }
        Path("/tmp/datelier-rebuild-gallery.json").write_text(
            json.dumps(report, indent=2)
        )
        print(json.dumps(report))


if __name__ == "__main__":
    main()
