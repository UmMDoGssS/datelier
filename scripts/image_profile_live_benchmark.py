"""Native responsiveness during an explicit complete mixed-image folder profile."""

import argparse
import hashlib
import json
import resource
from pathlib import Path
from tempfile import TemporaryDirectory
from time import perf_counter

import numpy as np
from imgui_bundle import hello_imgui
from PIL import Image
from rebuild_input import NativeInput

from datelier.application.editor import EditorController
from datelier.gui.app import InspectionEvidence, run_gui
from datelier.gui.components.probe import GuiProbe


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output", type=Path, default=Path("/tmp/datelier-image-profile-live.json")
    )
    args = parser.parse_args()
    stage = entered = 0
    started = 0.0
    running_frames: list[float] = []
    peak_cpu = peak_gpu = 0
    report: dict[str, object] = {}
    native = NativeInput()
    cold_baseline = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024
    baseline = cold_baseline
    with TemporaryDirectory(prefix="datelier-image-profile-live-") as directory:
        root = Path(directory)
        for index in range(100):
            mode = ("L", "RGB", "RGBA")[index % 3]
            value = (
                index
                if mode == "L"
                else (index, 20, 30)
                if mode == "RGB"
                else (index, 20, 30, 64)
            )
            Image.new(mode, (256, 256), value).save(root / f"{index:03}.png")
        before = {
            path: hashlib.sha256(path.read_bytes()).hexdigest()
            for path in root.iterdir()
        }

        def frame(
            editor: EditorController, probe: GuiProbe, evidence: InspectionEvidence
        ) -> None:
            nonlocal stage, entered, started, peak_cpu, peak_gpu, baseline
            file = editor.active
            active = file.loader.active
            if active is None:
                return
            params = hello_imgui.get_runner_params()
            age = evidence.frames - entered
            peak_cpu = max(peak_cpu, file.references.retained_bytes)
            peak_gpu = max(
                peak_gpu,
                int(
                    max(
                        (
                            v[0]
                            for k, v in probe.measurements.items()
                            if k.path[-1:] == ("preview-cache",)
                        ),
                        default=0,
                    )
                ),
            )
            if stage == 0:
                assert (
                    not file.images.profile_jobs.busy
                    and file.images.profile_jobs.active is None
                )
                file.profiles.choose(("path",))
                editor.choose_route("Profiles")
                stage, entered = 1, evidence.frames
            elif stage == 1 and age > 15 and not file.references.busy:
                if native.click(
                    probe, ("image-profile-settings", "prepare", "run"), evidence.frames
                ):
                    baseline = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024
                    started = perf_counter()
                    stage, entered = 4, evidence.frames
            native.advance(evidence.frames)
            if file.images.profile_jobs.busy and evidence.frame_intervals_ms:
                running_frames.append(evidence.frame_intervals_ms[-1])
            elif stage == 4 and file.images.profile_jobs.active is not None:
                profile = file.images.profile_jobs.active
                seconds = perf_counter() - started
                assert (
                    profile.ready == 100
                    and profile.total_pixels
                    == profile.profiled_pixels
                    == 100 * 256 * 256
                )
                assert not profile.sampled_pixels
                assert len(running_frames) > 20 and seconds < 10
                p95 = float(np.percentile(running_frames[5:], 95))
                assert p95 < 33
                assert (
                    peak_cpu <= file.references.settings.cpu_bytes
                    and peak_gpu <= file.references.settings.gpu_bytes
                )
                peak_rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024
                assert peak_rss <= 1024 * 1024 * 1024
                assert peak_rss - baseline < 96 * 1024 * 1024, (
                    (peak_rss - baseline) / 2**20,
                    peak_rss / 2**20,
                    baseline / 2**20,
                    peak_cpu,
                    peak_gpu,
                )
                report.update(
                    profile_seconds=seconds,
                    running_frames=len(running_frames),
                    running_frame_p95_ms=p95,
                    peak_preview_cpu_bytes=peak_cpu,
                    peak_preview_gpu_bytes=peak_gpu,
                    profile_result_bytes=profile.retained_bytes,
                    peak_rss_bytes=peak_rss,
                    baseline_rss_bytes=baseline,
                    cold_start_baseline_rss_bytes=cold_baseline,
                    startup_peak_increase_bytes=baseline - cold_baseline,
                    rss_increase_bytes=peak_rss - baseline,
                )
                params.app_shall_exit = True
                stage = 5

        evidence = run_gui(
            root,
            smoke_frames=2500,
            on_probe_frame=frame,
            preferences_path=root / "prefs.json",
        )
        assert stage == 5, (stage, evidence.frames, running_frames, report)
        assert all(
            hashlib.sha256(path.read_bytes()).hexdigest() == digest
            for path, digest in before.items()
        )
        report.update(
            frames=evidence.frames,
            images=100,
            dimensions=[256, 256],
            source_preserved=True,
        )
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, indent=2) + "\n")
        print(json.dumps(report))


if __name__ == "__main__":
    main()
