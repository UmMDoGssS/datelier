"""Cold native exact-corpus resource and UI gates with predeclared budgets."""

import argparse
import hashlib
import json
import resource
import subprocess
import sys
import threading
from pathlib import Path
from tempfile import TemporaryDirectory
from time import perf_counter
from unittest.mock import patch
from weakref import ref

import numpy as np
import polars as pl
from imgui_bundle import hello_imgui, imgui
from PIL import Image

from datelier.gui.app import InspectionEvidence, run_gui
from datelier.gui.editor_session import EditorSession
from datelier.gui.tabs import EditorTabs
from datelier.inspection.text.types import (
    CorpusMode,
    Normalization,
    TextScope,
    TextSettings,
    TextSource,
    TokenSettings,
)

BUDGETS = {
    "metadata_ms": 3000,
    "profile_ms": 20000,
    "frame_p95_ms": 33,
    "peak_rss_mib": 768,
    "profile_retained_bytes": 8 * 2**20,
    "rendered_frequency_rows": 20,
    "workers": 4,
    "temporary_bytes": 0,
}


def measure(source: Path, output: Path, *, snapshot: bool = False) -> dict[str, object]:
    stage = entered = 0
    started = perf_counter()
    command_started = 0.0
    pixels: dict[str, tuple[float, float]] = {}
    report: dict[str, object] = {"budgets": BUDGETS, "rows": 100000}
    original_button, original_tab = imgui.button, imgui.begin_tab_item
    profile_ref = None
    phases: list[tuple[int, int]] = []

    def capture(label: str) -> None:
        lo, hi = imgui.get_item_rect_min(), imgui.get_item_rect_max()
        pixels[label] = ((lo.x + hi.x) / 2, (lo.y + hi.y) / 2)

    def button(label: str, size: imgui.ImVec2 | None = None) -> bool:
        result = original_button(label, size)
        if label == "Calculate corpus profile":
            capture(label)
        return result

    def tab(
        label: str, p_open: bool | None = None, flags: int = 0
    ) -> tuple[bool, bool | None]:
        result = original_tab(label, p_open, flags)
        if label in ("Length distribution", "Token frequencies", "Statistics"):
            capture(label)
        return result

    def frame(
        editor: EditorSession, tabs: EditorTabs, evidence: InspectionEvidence
    ) -> None:
        nonlocal stage, entered, command_started, profile_ref
        file = editor.active
        if not phases or phases[-1][0] != stage:
            phases.append((stage, evidence.frames))
        jobs = file.text.jobs
        age = evidence.frames - entered
        io = imgui.get_io()

        def click(label: str, next_stage: int) -> None:
            nonlocal stage, entered
            io.mouse_pos = imgui.ImVec2(*pixels[label])
            io.want_set_mouse_pos = True
            stage, entered = next_stage, evidence.frames

        if stage == 0 and file.loader.active:
            file.exploration.profile.selection.columns = ("text",)
            file.exploration.tab = "Profiles"
            report["metadata_ms"] = (perf_counter() - started) * 1000
            assert jobs.profile is None and not jobs.busy
            jobs.settings = TextSettings(
                "text",
                TextSource.INLINE,
                tokens=TokenSettings(normalization=Normalization.NFC),
                scope=TextScope(CorpusMode.COLLECTION),
            )
            hello_imgui.get_runner_params().docking_params.focus_dockable_window(
                "Explore"
            )
            stage, entered = 1, evidence.frames
        elif stage == 1 and age > 10 and "Calculate corpus profile" in pixels:
            assert not jobs.busy and jobs.profile is None
            command_started = perf_counter()
            click("Calculate corpus profile", 2)
        elif stage in (2, 5, 9) and age > 3:
            io.add_mouse_button_event(0, True)
            stage, entered = stage + 1, evidence.frames
        elif stage in (3, 6, 10) and age > 3:
            io.add_mouse_button_event(0, False)
            stage, entered = stage + 1, evidence.frames
        elif stage == 4 and jobs.profile and file.text.profiles.shown > 5:
            prepared = jobs.profile
            profile = prepared.profile
            report["profile_ms"] = (perf_counter() - command_started) * 1000
            assert (
                profile.tokens,
                profile.documents,
                profile.nulls,
                profile.empty,
                profile.vocabulary_size,
            ) == (784000, 99000, 1000, 1000, 104)
            assert (
                profile.records.height == 100000 and profile.frequencies.height == 104
            )
            assert (
                len(prepared.frequency_labels) == 12
                and sum(prepared.length_counts) == 99000
            )
            assert profile.token_lengths.mean == 784000 / 99000
            report["profile_retained_bytes"] = prepared.retained_bytes
            report["exact_tokens"] = profile.tokens
            report["complete_frequency_types"] = profile.vocabulary_size
            report["temporary_bytes"] = 0
            output.mkdir(parents=True, exist_ok=True)
            click("Length distribution", 5)
        elif stage == 7 and file.text.profiles.plot_frames > 5 and age > 10:
            click("Token frequencies", 9)
        elif stage == 11 and age == 8:
            # Scroll over a command (outside the plot's zoom area) to expose
            # the complete virtual frequency table beneath the bounded chart.
            io.mouse_pos = imgui.ImVec2(*pixels["Calculate corpus profile"])
            io.want_set_mouse_pos = True
            io.add_mouse_wheel_event(0, -8)
        elif stage == 11 and file.text.profiles.rendered_frequency_rows and age > 100:
            report["rendered_frequency_rows"] = (
                file.text.profiles.rendered_frequency_rows
            )
            report["workers"] = sum(
                t.name.startswith("file_") for t in threading.enumerate()
            )
            profile_ref = ref(jobs.profile)
            if not snapshot:
                editor.close_tab(file.identity)
                assert profile_ref is not None and profile_ref() is None
            stage = 12
            hello_imgui.get_runner_params().app_shall_exit = True

    with (
        patch.object(imgui, "button", side_effect=button),
        patch.object(imgui, "begin_tab_item", side_effect=tab),
    ):
        evidence = run_gui(
            source,
            smoke_frames=2500,
            on_editor_frame=frame,
            preferences_path=source.parent / "prefs.json",
        )
    Image.fromarray(hello_imgui.final_app_window_screenshot()[:, :, :3]).save(
        output / ("text-profile-native.png" if snapshot else "text-profile-closed.png")
    )
    assert stage == 12, (stage, pixels)
    assert profile_ref is not None and profile_ref() is None
    report["profile_released_after_closure"] = True
    report["closure"] = "application" if snapshot else "file tab"
    report["frames"] = evidence.frames
    report["frame_p95_ms"] = float(np.percentile(evidence.frame_intervals_ms, 95))
    report["peak_rss_mib"] = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024
    report["workers_joined"] = not any(
        t.name.startswith("file_") for t in threading.enumerate()
    )
    report["phase_frame_p95_ms"] = {
        str(phase): float(np.percentile(evidence.frame_intervals_ms[start:stop], 95))
        for (phase, start), (_, stop) in zip(
            phases, phases[1:] + [(12, evidence.frames)], strict=True
        )
        if stop > start and evidence.frame_intervals_ms[start:stop]
    }
    for name, budget in BUDGETS.items():
        value = report[name]
        assert isinstance(value, (int, float))
        assert value <= budget, (name, value, budget)
    assert report["workers_joined"]
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path)
    parser.add_argument("--snapshot", action="store_true")
    parser.add_argument(
        "--output", type=Path, default=Path("/tmp/datelier-text-resources")
    )
    args = parser.parse_args()
    if args.source:
        print(json.dumps(measure(args.source, args.output, snapshot=args.snapshot)))
        return
    with TemporaryDirectory(prefix="datelier-text-profile-") as directory:
        source = Path(directory) / "corpus.parquet"
        pl.DataFrame(
            {
                "id": range(100000),
                "text": [
                    None
                    if i % 100 == 0
                    else ""
                    if i % 100 == 1
                    else f"alpha beta beta gamma δ 中 e\u0301 word{i % 100}"
                    for i in range(100000)
                ],
            }
        ).write_parquet(source)
        digest = hashlib.sha256(source.read_bytes()).hexdigest()
        completed = subprocess.run(
            [
                sys.executable,
                __file__,
                "--source",
                str(source),
                "--output",
                str(args.output),
                *(["--snapshot"] if args.snapshot else []),
            ],
            check=False,
            capture_output=True,
            text=True,
        )
        if completed.returncode:
            raise RuntimeError(completed.stderr)
        report = json.loads(completed.stdout.strip().splitlines()[-1])
        assert hashlib.sha256(source.read_bytes()).hexdigest() == digest
        report["source_preserved"] = True
        args.output.mkdir(parents=True, exist_ok=True)
        (
            args.output
            / (
                "text-profile-snapshot.json"
                if args.snapshot
                else "text-profile-resources.json"
            )
        ).write_text(json.dumps(report, indent=2) + "\n")
        print(json.dumps(report))


if __name__ == "__main__":
    main()
