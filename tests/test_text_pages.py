"""Original Unicode spans, full long-text navigation and retired page workers."""

from dataclasses import replace
from pathlib import Path
from threading import Event
from time import monotonic, sleep
from unittest.mock import patch
from uuid import uuid4

from datelier.core.dataset import DatasetRevision
from datelier.core.jobs import SharedWorkers
from datelier.gui.editor_session import EditorSession
from datelier.inspection.text.page_jobs import TextPageJobs
from datelier.inspection.text.pages import TextPage, display_text, prepare_text_page
from datelier.inspection.text.tokenization import TextTokenizer
from datelier.inspection.text.types import (
    Normalization,
    TextDocument,
    TextOrigin,
    TextStatus,
    TokenMode,
    TokenSettings,
)
from datelier.inspection.text.viewport import TextViewport
from datelier.io.types import ImportFormat, MediaOptions
from datelier.workspace.codec import decode_record, encode
from datelier.workspace.types import WorkspaceViews


def document(text: str) -> TextDocument:
    return TextDocument(
        TextOrigin("file", DatasetRevision(uuid4()), 0, "text"), TextStatus.READY, text
    )


def test_source_spans_survive_composition_expansion_and_control_display() -> None:
    original = "A e\u0301 ﬃ中🙂\n\t\0last"
    result = TextTokenizer(
        TokenSettings(TokenMode.CHARACTER, Normalization.NFKC)
    ).encode(document(original))
    accent = next(i for i, t in enumerate(result.tokens) if t.piece == "é")
    page = prepare_text_page(result, TextViewport(selected_token=accent))
    assert page.selected_source == "e\u0301" and page.selected_span == (2, 4)
    runs = tuple(r for line in page.lines for r in line.runs)
    assert "".join(r.text for r in runs) == display_text(original)
    assert [(r.start, r.end) for r in runs if r.highlighted] == [(2, 4)]
    assert result.document.text == original
    ligature = next(i for i, t in enumerate(result.tokens) if t.piece == "f")
    expanded = prepare_text_page(result, TextViewport(selected_token=ligature))
    assert expanded.selected_source == "ﬃ" and expanded.selected_span == (5, 6)


def test_long_pages_reach_every_code_point_and_final_token() -> None:
    original = ("e\u0301 中 🙂 abc\n" * 10000) + "FINAL"
    result = TextTokenizer(TokenSettings()).encode(document(original))
    assembled = []
    for start in range(0, len(original), 2048):
        page = prepare_text_page(result, TextViewport(start))
        assembled.append("".join(r.text for line in page.lines for r in line.runs))
        assert page.end - page.start <= 2048
    assert "".join(assembled) == display_text(original)
    final = prepare_text_page(
        result, TextViewport(len(original) - 128, 128, len(result.tokens) - 1)
    )
    assert final.end == len(original) and final.selected_source == "FINAL"
    assert final.selected_span == (len(original) - 5, len(original))
    assert len(final.lines) <= 128
    saved = WorkspaceViews(text=replace(WorkspaceViews().text, viewport=final.viewport))
    assert decode_record(WorkspaceViews, encode(saved)) == saved


def test_large_token_piece_is_navigable_independently_of_original_offsets() -> None:
    result = TextTokenizer(TokenSettings(TokenMode.WHITESPACE, lowercase=True)).encode(
        document("A" * 5000)
    )
    page = prepare_text_page(result, TextViewport(4000, 128, 0, 4744))
    assert page.selected_span == (0, 5000)
    assert page.piece_length == 5000 and page.selected_piece == "a" * 256
    assert page.piece_start == 4744 and page.start == 4000 and page.end == 4128
    assert all(r.highlighted for line in page.lines for r in line.runs)


def test_late_page_cannot_publish_into_replaced_or_closed_document() -> None:
    first = TextTokenizer(TokenSettings()).encode(document("first text"))
    second = TextTokenizer(TokenSettings()).encode(document("second text"))
    started, release = Event(), Event()
    workers = SharedWorkers()
    jobs = TextPageJobs(workers)
    original = prepare_text_page

    def slow(*args: object) -> TextPage:
        started.set()
        assert release.wait(3)
        return original(first, TextViewport())

    try:
        with patch(
            "datelier.inspection.text.page_jobs.prepare_text_page", side_effect=slow
        ):
            jobs.sync(first, TextViewport())
        assert started.wait(3)
        pending = jobs._future
        assert pending is not None
        jobs.sync(second, TextViewport())
        release.set()
        pending.result(3)
        deadline = monotonic() + 3
        while jobs.active is None and monotonic() < deadline:
            jobs.sync(second, TextViewport())
            sleep(0.001)
        assert jobs.active and jobs.active.origin == second.document.origin
        jobs.close()
        assert jobs.active is None and jobs._document is None
    finally:
        release.set()
        jobs.close()
        workers.shutdown()


def test_line_record_default_uses_one_line_and_supporting_identity(
    tmp_path: Path,
) -> None:
    path = tmp_path / "lines.txt"
    path.write_text("first line\nsecond 中🙂\n")
    editor = EditorSession()
    try:
        file = editor.active
        file.loader.request(
            path, MediaOptions(text_lines=True), format=ImportFormat.MEDIA
        )
        deadline = monotonic() + 5
        while file.loader.active is None and monotonic() < deadline:
            editor.poll()
            sleep(0.001)
        assert file.loader.active and file.text.jobs.settings.column == "text"
        file.text.request_record(file, "text", 1)
        deadline = monotonic() + 5
        while file.text.jobs.active is None and monotonic() < deadline:
            editor.poll()
            sleep(0.001)
        result = file.text.jobs.active
        assert result and result.document.text == "second 中🙂"
        assert (
            result.document.origin.row_id == 1
            and result.document.origin.file_id == file.identity
        )
        assert file.loader.active.dataset.table["line"].to_list() == [1, 2]
    finally:
        editor.close()


def test_character_offsets_keep_independent_combining_marks() -> None:
    raw = "e\u0301\u0303"
    original = document(raw)
    identity = TextTokenizer(TokenSettings(TokenMode.CHARACTER)).encode(original)
    assert [(t.piece, t.start, t.end) for t in identity.tokens] == [
        ("e", 0, 1),
        ("\u0301", 1, 2),
        ("\u0303", 2, 3),
    ]
    composed = TextTokenizer(
        TokenSettings(TokenMode.CHARACTER, Normalization.NFC)
    ).encode(original)
    assert [(t.piece, t.start, t.end) for t in composed.tokens] == [
        ("é", 0, 2),
        ("\u0303", 2, 3),
    ]
    first = prepare_text_page(identity, TextViewport(selected_token=0))
    assert first.selected_source == "e" and first.selected_span == (0, 1)
    second = prepare_text_page(composed, TextViewport(selected_token=1))
    assert second.selected_source == "\u0303" and second.selected_span == (2, 3)
