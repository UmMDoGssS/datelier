"""Native sizing across media/comparison families and repeated GPU closure."""

import argparse
import gc
import json
import os
import resource
from dataclasses import dataclass, replace
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import enumerate as threads
from time import perf_counter
from unittest.mock import patch
from weakref import ReferenceType, ref

import numpy as np
import polars as pl
import soundfile as sf
from imgui_bundle import hello_imgui
from numpy.typing import NDArray
from PIL import Image
from rebuild_input import NativeInput

from datelier.application.comparisons import ComparisonFamily
from datelier.application.sessions import EditorController
from datelier.gui.app import InspectionEvidence, run_gui
from datelier.gui.components.probe import GuiProbe
from datelier.inspection.audio.collections import AudioCollectionSettings
from datelier.inspection.audio.comparisons import (
    AudioComparisonSettings,
    AudioComparisonSource,
)
from datelier.inspection.audio.signal import AudioViewKind, SpectralView
from datelier.inspection.comparison_settings import ComparisonSettings, ComparisonSource
from datelier.inspection.images.comparisons.settings import (
    ImageComparisonSettings,
    ImageComparisonSource,
)
from datelier.inspection.images.profiles import ImageProfileSettings
from datelier.inspection.references import ReferenceSettings
from datelier.inspection.text.comparisons import (
    TextComparisonSettings,
    TextComparisonSource,
)
from datelier.inspection.text.types import TextSource
from datelier.workspace.preferences import Preferences, Theme, save_preferences

ROUTES = (
    "image",
    "caption",
    "audio",
    "audio-spectral",
    "pixels",
    "Profiles",
    "profile-text-Length distribution",
    "profile-text-Token frequencies",
    "profile-image-Dimensions",
    "profile-image-Colors",
    "Columns",
    "Text",
    "Images",
    "Audio",
)


@dataclass
class TrackedTexture:
    """Transparent native-handle owner: the binding itself lacks weakrefs."""

    native: hello_imgui.TextureGpu

    @property
    def width(self) -> int:
        return self.native.width

    @property
    def height(self) -> int:
        return self.native.height

    def texture_id(self) -> int:
        return self.native.texture_id()


def rss_mib() -> float:
    pages = int(Path("/proc/self/statm").read_text().split()[1])
    return pages * os.sysconf("SC_PAGE_SIZE") / 2**20


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--width", type=int, default=1280)
    parser.add_argument("--height", type=int, default=800)
    parser.add_argument("--theme", choices=tuple(Theme), default=Theme.DARK)
    parser.add_argument(
        "--output", type=Path, default=Path("/tmp/datelier-media-matrix.json")
    )
    args = parser.parse_args()
    with TemporaryDirectory(prefix="datelier-media-matrix-") as directory:
        root = Path(directory)
        Image.new("RGB", (48, 32), (80, 20, 30)).save(root / "image.png")
        sf.write(root / "audio.wav", np.sin(np.arange(8000) / 10), 8000)
        for name in ("first", "second"):
            pl.DataFrame(
                {
                    "image": ["image.png"] * 3,
                    "audio": ["audio.wav"] * 3,
                    "caption": ["A e\u0301 文本 ###", "b c", "d"],
                    "x": [1.0, 3.0, 2.0],
                }
            ).write_csv(root / f"{name}.csv")
        np.savez_compressed(
            root / "array.npz",
            pixels=np.stack(
                [np.full((32, 48), r * 30, dtype=np.uint8) for r in range(8)]
            ),
        )
        originals = {p: p.read_bytes() for p in root.iterdir()}
        prefs = root / "preferences.json"
        save_preferences(prefs, Preferences(theme=Theme(args.theme)))
        native = NativeInput()
        phase = route = action = cycle = entered = 0
        configured = False
        ids: tuple[str, ...] = ()
        viewport_paths: list[tuple[str, ...]] = []
        exercised: list[str] = []
        viewport_index = 0
        before = 0.0
        max_gpu = max_pending = max_workers = 0
        max_close_ms = 0.0
        cycle_baseline = 0.0
        retained_growth = 0
        ready_at = 0.0
        preview_times: list[float] = []
        owning: EditorController | None = None
        done = False
        allocations: list[tuple[ReferenceType[TrackedTexture], int]] = []
        create_texture = hello_imgui.create_texture_gpu_from_rgba_data

        def tracked_texture(rgba: NDArray[np.uint8]) -> TrackedTexture:
            texture = TrackedTexture(create_texture(rgba))
            allocations.append((ref(texture), rgba.nbytes))
            return texture

        def frame(
            editor: EditorController, probe: GuiProbe, evidence: InspectionEvidence
        ) -> None:
            nonlocal \
                phase, \
                route, \
                action, \
                cycle, \
                entered, \
                configured, \
                ids, \
                viewport_paths, \
                viewport_index
            nonlocal \
                before, \
                max_gpu, \
                max_pending, \
                max_workers, \
                max_close_ms, \
                cycle_baseline, \
                retained_growth
            nonlocal ready_at, owning, done
            owning = editor
            gpu = sum(
                size for reference, size in allocations if reference() is not None
            )
            max_gpu = max(max_gpu, int(gpu))
            max_pending = max(max_pending, editor.workers.pending)
            max_workers = max(
                max_workers, sum(t.name.startswith("file_") for t in threads())
            )
            assert max_workers <= 4
            assert gpu <= 3 * 1024 * 1024
            assert evidence.frames < 2200, (
                phase,
                route,
                action,
                viewport_paths,
                [k.path for k in probe.targets],
            )
            if native.advance(evidence.frames):
                return
            age = evidence.frames - entered
            if phase == 0 and editor.current.inspection and evidence.frames > 15:
                editor.new_file(root / "second.csv")
                editor.new_file(root / "array.npz")
                ids = tuple(f.identity for f in editor.files)
                phase = 1
            elif (
                phase == 1
                and all(f.inspection for f in editor.files)
                and not editor.workers.pending
            ):
                for file in editor.files:
                    file.references.configure(
                        ReferenceSettings(
                            roots=(str(root),),
                            cpu_bytes=1024 * 1024,
                            gpu_bytes=1024 * 1024,
                        )
                    )
                    file.records.settings = replace(
                        file.records.settings, count=3, gallery=False
                    )
                a, b = ids[:2]
                editor.compare.columns.draft = ComparisonSettings(
                    tuple(ComparisonSource(i, "x") for i in (a, b))
                )
                editor.compare.text.draft = TextComparisonSettings(
                    tuple(
                        TextComparisonSource(i, "caption", TextSource.INLINE)
                        for i in (a, b)
                    )
                )
                editor.compare.images.draft = ImageComparisonSettings(
                    tuple(
                        ImageComparisonSource(i, ImageProfileSettings("image"))
                        for i in (a, b)
                    )
                )
                editor.compare.audio.draft = AudioComparisonSettings(
                    tuple(
                        AudioComparisonSource(i, AudioCollectionSettings("audio"))
                        for i in (a, b)
                    )
                )
                editor.compare.columns.apply()
                phase, entered = 2, evidence.frames
            elif phase == 2:
                if not configured:
                    editor.activate(ids[2] if ROUTES[route] == "pixels" else ids[0])
                    file = editor.current
                    name = ROUTES[route]
                    print("route", name, flush=True)
                    if name in (
                        "image",
                        "caption",
                        "audio",
                        "audio-spectral",
                        "pixels",
                    ):
                        file.records.settings = replace(
                            file.records.settings,
                            primary="audio" if name == "audio-spectral" else name,
                            gallery=False,
                        )
                        if name == "audio-spectral":
                            file.audio.settings = replace(
                                file.audio.settings,
                                view=replace(
                                    file.audio.settings.view,
                                    mode=AudioViewKind.SPECTROGRAM,
                                ),
                            )
                        editor.choose_route("Inspect")
                    elif name == "Profiles":
                        file.profiles.choose(("x",))
                        editor.choose_route("Profiles")
                    elif name.startswith("profile-text-"):
                        file.profiles.choose(("caption",))
                        file.profiles.text = True
                        file.text.profile_tab = name.removeprefix("profile-text-")
                        file.text.request_profile("caption")
                        editor.choose_route("Profiles")
                    elif name.startswith("profile-image-"):
                        file.profiles.choose(("image",))
                        file.images.settings = replace(
                            file.images.settings,
                            profile_view=replace(
                                file.images.settings.profile_view,
                                tab=name.removeprefix("profile-image-"),
                            ),
                        )
                        file.images.request_collection("image")
                        editor.choose_route("Profiles")
                    else:
                        editor.choose_route("Compare files")
                        editor.compare.tab = ComparisonFamily(name)
                        if name == "Text":
                            editor.compare.text.prepare()
                        elif name == "Images":
                            editor.compare.images.prepare()
                        elif name == "Audio":
                            editor.compare.audio.prepare()
                    configured, entered = True, evidence.frames
                    return
                file = editor.current
                name = ROUTES[route]
                if (
                    name == "caption"
                    and file.text.jobs.active is None
                    and age > 5
                    and not file.text.jobs.busy
                ):
                    file.text.request_record("caption", 0)
                if (
                    name == "audio"
                    and file.audio.jobs.metadata
                    and file.audio.signal.active is None
                    and not file.audio.signal.busy
                ):
                    file.audio.request_signal()
                if (
                    name == "audio-spectral"
                    and file.audio.jobs.metadata
                    and not isinstance(file.audio.signal.active, SpectralView)
                    and not file.audio.signal.busy
                ):
                    file.audio.request_signal()
                if age < 12 or editor.workers.pending:
                    return
                viewport_paths = list(
                    dict.fromkeys(
                        k.path[:-1] for k in probe.targets if k.path[-1] == "expand"
                    )
                )
                if not viewport_paths:
                    assert age < 100, (
                        name,
                        editor.compare.text.message,
                        editor.compare.images.message,
                        editor.compare.audio.message,
                    )
                    return
                viewport_index = action = 0
                phase, entered = 3, evidence.frames
            elif phase == 3:
                path = viewport_paths[viewport_index]

                def measure(key: str) -> tuple[float, float] | None:
                    return next(
                        (
                            v
                            for k, v in probe.measurements.items()
                            if k.path == (*path, key)
                        ),
                        None,
                    )

                if action == 0:
                    value = measure("extent")
                    point = native.find(probe, (*path, "resize"))
                    if not value or not point:
                        return
                    before = value[0]
                    if native.click(probe, (*path, "resize"), evidence.frames):
                        native.drag(point, (point[0], point[1] + 35), evidence.frames)
                        action, entered = 1, evidence.frames
                elif action == 1 and age > 3:
                    value = measure("extent")
                    assert value and value[0] >= before + 30, (
                        ROUTES[route],
                        path,
                        before,
                        value,
                    )
                    if native.click(probe, (*path, "expand"), evidence.frames):
                        action, entered = 2, evidence.frames
                elif action == 2 and age > 3:
                    value = measure("extent")
                    assert value and value[1] == 1, (path, value)
                    if native.click(probe, (*path, "restore"), evidence.frames):
                        action, entered = 3, evidence.frames
                elif action == 3 and age > 3:
                    value = measure("extent")
                    assert value and value[1] == 0
                    if native.click(probe, (*path, "auto"), evidence.frames):
                        action, entered = 4, evidence.frames
                elif action == 4 and age > 3:
                    value = measure("sizing")
                    assert value and value == (0, 0), (path, value)
                    assert not editor.playback.snapshot.request
                    assert all(not f.analysis.jobs.results for f in editor.all_files)
                    exercised.append(ROUTES[route] + "/" + "/".join(path))
                    viewport_index += 1
                    action = 0
                    if viewport_index == len(viewport_paths):
                        route += 1
                        if route == len(ROUTES):
                            phase = 4
                        else:
                            phase, configured, entered = 2, False, evidence.frames
            elif phase == 4:
                start = perf_counter()
                for identity in tuple(f.identity for f in editor.files):
                    editor.close_file(identity)
                max_close_ms = max(max_close_ms, (perf_counter() - start) * 1000)
                phase, entered = 5, evidence.frames
            elif phase == 5 and age > 8 and not editor.workers.pending:
                assert gpu == 0, gpu
                gc.collect()
                if cycle == 0:
                    cycle_baseline = rss_mib()
                if cycle == 6:
                    retained_growth = rss_mib() - cycle_baseline
                    assert retained_growth <= 96
                    assert max_close_ms <= 33
                    assert all(p.read_bytes() == raw for p, raw in originals.items())
                    done = True
                    hello_imgui.get_runner_params().app_shall_exit = True
                    return
                file = editor.new_file(
                    root / ("array.npz" if cycle % 2 else "first.csv")
                )
                ids = (file.identity,)
                ready_at = perf_counter()
                phase, entered = 6, evidence.frames
            elif phase == 6 and editor.current.inspection:
                file = editor.current
                file.references.configure(
                    ReferenceSettings(
                        roots=(str(root),), cpu_bytes=1024 * 1024, gpu_bytes=1024 * 1024
                    )
                )
                file.records.settings = replace(
                    file.records.settings,
                    primary="pixels" if cycle % 2 else "image",
                    gallery=True,
                    count=3,
                )
                editor.choose_route("Inspect")
                phase, entered = 7, evidence.frames
            elif phase == 7 and gpu > 0 and age > 12:
                preview_times.append((perf_counter() - ready_at) * 1000)
                assert preview_times[-1] <= 2000
                cycle += 1
                phase = 4

        with patch.object(
            hello_imgui, "create_texture_gpu_from_rgba_data", tracked_texture
        ):
            evidence = run_gui(
                root / "first.csv",
                window_size=(args.width, args.height),
                preferences_path=prefs,
                on_probe_frame=frame,
            )
        assert done and owning and owning.closed
        assert not any(t.name.startswith("file_") for t in threads())
        peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024
        p95 = float(np.percentile(evidence.frame_intervals_ms, 95))
        assert p95 <= 33 and peak <= 1024, (p95, peak)
        report = {
            "size": [args.width, args.height],
            "theme": args.theme,
            "frames": evidence.frames,
            "p95_ms": p95,
            "viewports": exercised,
            "gpu_cycles": cycle,
            "peak_gpu_bytes": max_gpu,
            "gpu_after_every_close": 0,
            "peak_rss_mib": peak,
            "retained_growth_mib": retained_growth,
            "max_close_ms": max_close_ms,
            "workers": max_workers,
            "max_outstanding": max_pending,
            "preview_ms": preview_times,
            "source_preserved": True,
            "implicit_ml_training_playback": 0,
        }
        args.output.write_text(json.dumps(report, indent=2) + "\n")
        print(json.dumps(report))


if __name__ == "__main__":
    main()
