"""Cold mixed-corpus/long-record native gates with predeclared resource budgets."""

import argparse
import hashlib
import json
import resource
import subprocess
import sys
import threading
from dataclasses import replace
from pathlib import Path
from tempfile import TemporaryDirectory
from time import perf_counter
from unittest.mock import patch
from weakref import ReferenceType, ref

import numpy as np
import polars as pl
from imgui_bundle import hello_imgui, imgui
from PIL import Image

from datelier.gui.app import InspectionEvidence, run_gui
from datelier.gui.editor_session import EditorSession
from datelier.gui.tabs import EditorTabs
from datelier.gui.text.comparison_charts import frequency_table
from datelier.inspection.text.comparisons.settings import (
    TextComparisonSettings,
    TextComparisonSource,
)
from datelier.inspection.text.comparisons.types import PreparedTextComparison
from datelier.inspection.text.types import (
    CorpusMode,
    Normalization,
    TextScope,
    TextSettings,
    TextSource,
    TokenizedDocument,
    TokenMode,
    TokenSettings,
)
from datelier.inspection.text.viewport import TextViewport

BUDGETS = {
    "metadata_ms": 3000,
    "comparison_ms": 20000,
    "long_record_ms": 3000,
    "frame_p95_ms": 33,
    "long_prepare_frame_p95_ms": 33,
    "peak_rss_mib": 768,
    "comparison_retained_bytes": 8 * 2**20,
    "rendered_frequency_rows": 20,
    "rendered_token_rows": 30,
    "source_page_code_points": 2048,
    "workers": 4,
    "temporary_bytes": 0,
}


def measure(root: Path, output: Path) -> dict[str, object]:
    stage = entered = 0
    started = perf_counter()
    command_started = long_started = 0.0
    pixels: dict[str, tuple[float, float]] = {}
    report: dict[str, object] = {"budgets": BUDGETS, "corpus_rows": 100000}
    comparison_ref: ReferenceType[PreparedTextComparison] | None = None
    document_ref: ReferenceType[TokenizedDocument] | None = None
    pointer: tuple[float, float] | None = None
    original_tab = imgui.begin_tab_item
    rendered = token_rows = 0
    phases: list[tuple[int, int]] = []

    def table(result: PreparedTextComparison, documents: bool) -> int:
        nonlocal rendered
        count = frequency_table(result, documents)
        rendered = max(rendered, count)
        return count

    def tab(
        label: str, p_open: bool | None = None, flags: int = 0
    ) -> tuple[bool, bool | None]:
        # Resource probes choose the heavy view directly; mouse interaction
        # with these same tabs is verified by text_comparison_smoke.py.
        if label == "Token frequencies" and 7 <= stage <= 9:
            flags |= imgui.TabItemFlags_.set_selected
        result = original_tab(label, p_open, flags)
        lo, hi = imgui.get_item_rect_min(), imgui.get_item_rect_max()
        pixels[label] = ((lo.x + hi.x) / 2, (lo.y + hi.y) / 2)
        return result

    def frame(
        editor: EditorSession, tabs: EditorTabs, evidence: InspectionEvidence
    ) -> None:
        nonlocal \
            stage, \
            entered, \
            command_started, \
            long_started, \
            comparison_ref, \
            document_ref, \
            token_rows
        if not phases or phases[-1][0] != stage:
            phases.append((stage, max(0, evidence.frames - 11)))
        age = evidence.frames - entered
        io = imgui.get_io()
        if pointer is not None:
            io.add_mouse_pos_event(*pointer)
            io.mouse_pos = imgui.ImVec2(*pointer)
            io.want_set_mouse_pos = True
        params = hello_imgui.get_runner_params()

        def click(label: str, next_stage: int) -> None:
            nonlocal stage, entered, pointer
            pointer = pixels[label]
            io.add_mouse_pos_event(*pointer)
            io.mouse_pos = imgui.ImVec2(*pointer)
            io.want_set_mouse_pos = True
            stage, entered = next_stage, evidence.frames

        def focus(name: str) -> None:
            window = imgui.internal.find_window_by_name(name)
            imgui.internal.set_window_dock(window, 0, imgui.Cond_.always)
            imgui.set_window_pos(name, (20, 65), imgui.Cond_.always)
            imgui.set_window_size(name, (1120, 725), imgui.Cond_.always)
            params.docking_params.focus_dockable_window(name)

        if stage == 0:
            editor.opening.request(
                tuple(
                    root / name for name in ("a.parquet", "b.parquet", "long.parquet")
                ),
                editor.active_id,
            )
            stage = 1
        elif (
            stage == 1
            and len(editor.files) == 3
            and all(f.loader.active for f in editor.files)
        ):
            report["metadata_ms"] = (perf_counter() - started) * 1000
            editor.text_comparisons = (
                TextComparisonSettings(
                    tuple(
                        TextComparisonSource(
                            f.identity,
                            "text",
                            TextSource.INLINE,
                            scope=TextScope(CorpusMode.COLLECTION),
                        )
                        for f in editor.files[:2]
                    ),
                    tokens=TokenSettings(normalization=Normalization.NFC),
                ),
            )
            assert (
                not editor.text_comparison_jobs.busy
                and editor.text_comparison_jobs.active is None
            )
            focus("Compare files")
            stage, entered = 2, evidence.frames
        elif stage == 2 and age > 10:
            click("Text corpora", 3)
        elif stage in (3, 7) and age > 3:
            io.add_mouse_button_event(0, True)
            stage, entered = stage + 1, evidence.frames
        elif stage in (4, 8) and age > 3:
            io.add_mouse_button_event(0, False)
            stage, entered = stage + 1, evidence.frames
        elif stage == 5 and age > 10:
            command_started = perf_counter()
            editor.text_comparison_jobs.request()
            stage = 6
        elif (
            stage == 6
            and editor.text_comparison_jobs.active
            and "Token frequencies" in pixels
        ):
            result = editor.text_comparison_jobs.active
            assert [p.tokens for p in result.profiles] == [392000, 392000]
            assert [p.documents for p in result.profiles] == [49500, 49500]
            assert all(
                p.records.height == 50000 and p.frequencies.height == 104
                for p in result.profiles
            )
            assert (
                result.frequencies.height == 104 and len(result.frequency_labels) == 12
            )
            report["comparison_ms"] = (perf_counter() - command_started) * 1000
            report["comparison_retained_bytes"] = result.retained_bytes
            report["exact_tokens"] = 784000
            comparison_ref = ref(result)
            click("Token frequencies", 7)
        elif stage == 9 and age > 100 and rendered:
            report["rendered_frequency_rows"] = rendered
            file = editor.files[2]
            editor.activate(file.identity)
            file.inspect.settings = replace(
                file.inspect.settings, primary="text", supporting=("id",), gallery=False
            )
            file.text.jobs.settings = TextSettings(
                "text",
                TextSource.INLINE,
                tokens=TokenSettings(TokenMode.CHARACTER, Normalization.NFC),
            )
            file.text.sync(file)
            long_started = perf_counter()
            file.text.jobs.request_document()
            file.exploration.tab = "Inspect"
            focus("Explore")
            stage, entered = 10, evidence.frames
        elif stage == 10 and editor.files[2].text.jobs.active:
            file = editor.files[2]
            document = file.text.jobs.active
            assert document
            assert (
                len(document.document.text) == 110013 and len(document.tokens) == 110012
            )
            report["long_record_ms"] = (perf_counter() - long_started) * 1000
            report["original_code_points"] = len(document.document.text)
            report["complete_record_tokens"] = len(document.tokens)
            file.text.jobs.settings = replace(
                file.text.jobs.settings,
                viewport=TextViewport(
                    start=len(document.document.text) - 2048,
                    selected_token=len(document.tokens) - 1,
                ),
            )
            document_ref = ref(document)
            stage, entered = 11, evidence.frames
        elif stage == 11 and age > 100 and editor.files[2].text.pages.active:
            file = editor.files[2]
            page = file.text.pages.active
            assert page and page.end == 110013 and page.selected_source == "L"
            assert "FINAL" in "".join(r.text for line in page.lines for r in line.runs)
            token_rows = max(token_rows, file.text.document.rendered_tokens)
            report["rendered_token_rows"] = token_rows
            report["source_page_code_points"] = page.end - page.start
            report["workers"] = sum(
                t.name.startswith("file_") for t in threading.enumerate()
            )
            report["temporary_bytes"] = 0
            editor.close_tab(editor.files[0].identity)
            editor.close_tab(file.identity)
            stage, entered = 12, evidence.frames
        elif stage == 12 and age > 15:
            assert comparison_ref and comparison_ref() is None
            assert document_ref and document_ref() is None
            report["results_released_after_tab_closure"] = True
            stage = 13
            params.app_shall_exit = True

    with (
        patch.object(imgui, "begin_tab_item", side_effect=tab),
        patch("datelier.gui.text.comparison_view.frequency_table", new=table),
    ):
        evidence = run_gui(
            smoke_frames=2000,
            on_editor_frame=frame,
            preferences_path=root / "prefs.json",
        )
    output.mkdir(parents=True, exist_ok=True)
    Image.fromarray(hello_imgui.final_app_window_screenshot()[:, :, :3]).save(
        output / "text-mixed-closed.png"
    )
    assert stage == 13, (stage, pixels, report)
    report["frames"] = evidence.frames
    report["frame_p95_ms"] = float(np.percentile(evidence.frame_intervals_ms, 95))
    report["peak_rss_mib"] = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024
    report["workers_joined"] = not any(
        t.name.startswith("file_") for t in threading.enumerate()
    )
    report["phase_frame_p95_ms"] = {
        str(phase): float(np.percentile(evidence.frame_intervals_ms[start:stop], 95))
        for (phase, start), (_, stop) in zip(
            phases, phases[1:] + [(13, len(evidence.frame_intervals_ms))], strict=True
        )
        if stop > start
    }
    report["long_prepare_frame_p95_ms"] = report["phase_frame_p95_ms"]["10"]
    for name, budget in BUDGETS.items():
        value = report[name]
        assert isinstance(value, (int, float))
        assert value <= budget, (name, value, budget)
    assert report["workers_joined"] and token_rows > 0
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path)
    parser.add_argument("--output", type=Path, default=Path("/tmp/datelier-text-mixed"))
    args = parser.parse_args()
    if args.root:
        print(json.dumps(measure(args.root, args.output)))
        return
    with TemporaryDirectory(prefix="datelier-text-mixed-") as directory:
        root = Path(directory)
        for name in ("a", "b"):
            pl.DataFrame(
                {
                    "id": range(50000),
                    "text": [
                        None
                        if i % 100 == 0
                        else ""
                        if i % 100 == 1
                        else f"alpha beta beta gamma δ 中 e\u0301 word{i % 100}"
                        for i in range(50000)
                    ],
                }
            ).write_parquet(root / f"{name}.parquet")
        text = "A e\u0301 中🙂\n" + "long original text 中🙂\n" * 5000 + "FINAL"
        pl.DataFrame({"id": [1], "text": [text]}).write_parquet(root / "long.parquet")
        sources = tuple(
            root / name for name in ("a.parquet", "b.parquet", "long.parquet")
        )
        digests = [hashlib.sha256(p.read_bytes()).hexdigest() for p in sources]
        child = subprocess.run(
            [
                sys.executable,
                __file__,
                "--root",
                str(root),
                "--output",
                str(args.output),
            ],
            capture_output=True,
            text=True,
        )
        if child.returncode:
            raise RuntimeError(child.stderr)
        assert digests == [hashlib.sha256(p.read_bytes()).hexdigest() for p in sources]
        report = json.loads(child.stdout.strip().splitlines()[-1])
        report["sources_preserved"] = True
        (args.output / "text-mixed-resources.json").write_text(
            json.dumps(report, indent=2) + "\n"
        )
        print(json.dumps(report))


if __name__ == "__main__":
    main()
