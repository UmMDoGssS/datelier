"""Prepared-state native instrumentation shared by the retained text benchmarks."""

import json
import resource
import sys
import threading
from dataclasses import replace
from pathlib import Path
from time import perf_counter
from weakref import ReferenceType, ref

import numpy as np
from imgui_bundle import hello_imgui

from datelier.application.comparisons.base import ComparisonFamily
from datelier.application.editor import EditorController
from datelier.gui.app import InspectionEvidence, run_gui
from datelier.gui.components.probe import GuiProbe
from datelier.inspection.text.comparisons import (
    TextComparisonSettings,
    TextComparisonSource,
)
from datelier.inspection.text.comparisons.types import PreparedTextComparison
from datelier.inspection.text.display import TextViewport
from datelier.inspection.text.profiles.prepare import PreparedTextProfile
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


def rendered(probe: GuiProbe, key: str) -> int:
    return int(
        max(
            (
                v[0]
                for k, v in probe.measurements.items()
                if k.path[-2:] == (key, "rendered-rows")
            ),
            default=0,
        )
    )


def finish(
    evidence: InspectionEvidence, report: dict[str, object], budgets: dict[str, int]
) -> dict[str, object]:
    report.update(
        frames=evidence.frames,
        frame_p95_ms=float(np.percentile(evidence.frame_intervals_ms, 95)),
        peak_rss_mib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024,
    )
    for name, budget in budgets.items():
        value = report[name]
        if isinstance(value, (int, float)) and value > budget:
            print(json.dumps(report), file=sys.stderr)
        assert isinstance(value, (int, float)) and value <= budget, (
            name,
            value,
            budget,
        )
    return report


def measure_profile(
    source: Path, budgets: dict[str, int], snapshot: bool
) -> dict[str, object]:
    started = perf_counter()
    command_started = 0.0
    stage = entered = frequency_rows = 0
    profile_ref: ReferenceType[PreparedTextProfile] | None = None
    report: dict[str, object] = {"budgets": budgets, "rows": 100000}

    def frame(
        editor: EditorController, probe: GuiProbe, evidence: InspectionEvidence
    ) -> None:
        nonlocal stage, entered, command_started, frequency_rows, profile_ref
        file = editor.current
        assert evidence.frames < 4000, (stage, file.text.corpus.message)
        if stage == 0 and file.inspection:
            report["metadata_ms"] = (perf_counter() - started) * 1000
            assert file.text.corpus.profile is None and not file.text.corpus.busy
            file.profiles.choose(("text",))
            file.profiles.text = True
            file.profiles.height = 170
            file.text.jobs.settings = TextSettings(
                "text",
                TextSource.INLINE,
                tokens=TokenSettings(normalization=Normalization.NFC),
                scope=TextScope(CorpusMode.COLLECTION),
            )
            editor.choose_route("Profiles")
            command_started = perf_counter()
            file.text.request_profile("text")
            stage = 1
        elif stage == 1 and file.text.corpus.profile:
            prepared = file.text.corpus.profile
            profile = prepared.profile
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
            report.update(
                profile_ms=(perf_counter() - command_started) * 1000,
                profile_retained_bytes=prepared.retained_bytes,
                exact_tokens=profile.tokens,
                complete_frequency_types=profile.vocabulary_size,
                temporary_bytes=0,
            )
            file.text.profile_tab = "Token frequencies"
            profile_ref = ref(prepared)
            stage, entered = 2, evidence.frames
        elif stage == 2 and evidence.frames - entered > 15:
            frequency_rows = max(frequency_rows, rendered(probe, "all-frequencies"))
            if not frequency_rows:
                return
            report.update(
                rendered_frequency_rows=frequency_rows,
                workers=sum(t.name.startswith("file_") for t in threading.enumerate()),
            )
            if snapshot:
                stage = 4
                hello_imgui.get_runner_params().app_shall_exit = True
            else:
                editor.close_file(file.identity)
                stage, entered = 3, evidence.frames
        elif (
            stage == 3 and evidence.frames - entered > 8 and not editor.workers.pending
        ):
            assert profile_ref is not None and profile_ref() is None
            report["results_released_after_tab_closure"] = True
            stage = 4
            hello_imgui.get_runner_params().app_shall_exit = True

    evidence = run_gui(source, on_probe_frame=frame)
    assert stage == 4
    return finish(evidence, report, budgets)


def measure_mixed(root: Path, budgets: dict[str, int]) -> dict[str, object]:
    stage = entered = frequency_rows = token_rows = 0
    started = perf_counter()
    command_started = long_started = 0.0
    comparison_ref: ReferenceType[PreparedTextComparison] | None = None
    document_ref: ReferenceType[TokenizedDocument] | None = None
    report: dict[str, object] = {"budgets": budgets, "corpus_rows": 100000}
    long_frames: list[float] = []

    def frame(
        editor: EditorController, probe: GuiProbe, evidence: InspectionEvidence
    ) -> None:
        nonlocal \
            stage, \
            entered, \
            command_started, \
            long_started, \
            comparison_ref, \
            document_ref, \
            frequency_rows, \
            token_rows
        assert evidence.frames < 4000, (stage, editor.compare.text.message)
        if stage == 0:
            editor.open_paths(
                tuple(
                    root / name for name in ("a.parquet", "b.parquet", "long.parquet")
                )
            )
            stage = 1
        elif (
            stage == 1
            and len(editor.files) == 3
            and all(f.inspection for f in editor.files)
            and not editor.workers.pending
        ):
            report["metadata_ms"] = (perf_counter() - started) * 1000
            model = editor.compare.text
            model.draft = TextComparisonSettings(
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
            )
            editor.choose_route("Compare files")
            editor.compare.tab = ComparisonFamily.TEXT
            model.view = replace(model.view, tab="Token frequencies", height=170)
            assert model.active is None and not model.jobs.busy
            command_started = perf_counter()
            model.prepare()
            stage = 2
        elif stage == 2 and editor.compare.text.active:
            result = editor.compare.text.active
            assert result and sum(p.tokens for p in result.profiles) == 784000
            assert sum(p.documents for p in result.profiles) == 99000
            assert len(result.frequencies) == 104
            report.update(
                comparison_ms=(perf_counter() - command_started) * 1000,
                comparison_retained_bytes=result.retained_bytes,
                exact_tokens=784000,
            )
            comparison_ref = ref(result)
            stage, entered = 3, evidence.frames
        elif stage == 3 and evidence.frames - entered > 15:
            frequency_rows = max(frequency_rows, rendered(probe, "all-frequencies"))
            if not frequency_rows:
                return
            report["rendered_frequency_rows"] = frequency_rows
            file = editor.files[2]
            editor.activate(file.identity)
            file.records.settings = replace(
                file.records.settings, primary="text", supporting=("id",), gallery=False
            )
            file.text.jobs.settings = TextSettings(
                "text",
                TextSource.INLINE,
                tokens=TokenSettings(TokenMode.CHARACTER, Normalization.NFC),
            )
            editor.choose_route("Inspect")
            stage, entered = 4, evidence.frames
        elif stage == 4 and evidence.frames - entered > 5:
            long_started = perf_counter()
            editor.current.text.request_record("text", 0)
            stage = 5
        elif stage == 5:
            if evidence.frame_intervals_ms:
                long_frames.append(evidence.frame_intervals_ms[-1])
            file = editor.current
            document = file.text.jobs.active
            if document is None:
                return
            assert (
                len(document.document.text) == 110013 and len(document.tokens) == 110012
            )
            report.update(
                long_record_ms=(perf_counter() - long_started) * 1000,
                original_code_points=len(document.document.text),
                complete_record_tokens=len(document.tokens),
            )
            file.text.jobs.settings = replace(
                file.text.jobs.settings,
                viewport=TextViewport(
                    start=len(document.document.text) - 2048,
                    selected_token=len(document.tokens) - 1,
                ),
            )
            document_ref = ref(document)
            stage, entered = 6, evidence.frames
        elif (
            stage == 6
            and evidence.frames - entered > 20
            and editor.current.text.pages.active
        ):
            page = editor.current.text.pages.active
            assert page and page.end == 110013 and page.selected_source == "L"
            assert "FINAL" in "".join(r.text for line in page.lines for r in line.runs)
            token_rows = max(token_rows, rendered(probe, "token-rows"))
            if not token_rows:
                return
            report.update(
                rendered_token_rows=token_rows,
                source_page_code_points=page.end - page.start,
                workers=sum(t.name.startswith("file_") for t in threading.enumerate()),
                temporary_bytes=0,
            )
            editor.close_file(editor.files[0].identity)
            editor.close_file(editor.current.identity)
            stage, entered = 7, evidence.frames
        elif (
            stage == 7 and evidence.frames - entered > 8 and not editor.workers.pending
        ):
            assert comparison_ref is not None and comparison_ref() is None
            assert document_ref is not None and document_ref() is None
            report["results_released_after_tab_closure"] = True
            stage = 8
            hello_imgui.get_runner_params().app_shall_exit = True

    evidence = run_gui(on_probe_frame=frame)
    assert stage == 8
    report["long_prepare_frame_p95_ms"] = float(np.percentile(long_frames, 95))
    return finish(evidence, report, budgets)
