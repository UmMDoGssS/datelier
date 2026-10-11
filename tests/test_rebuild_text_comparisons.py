"""Explicit shared tokenization, named/list scopes, draft independence and restore."""

import json
from dataclasses import replace
from pathlib import Path

from test_rebuild_comparisons import until

from datelier.application.editor import EditorController
from datelier.application.workspace import capture_session
from datelier.inspection.text.comparisons.settings import TextComparisonViewSettings
from datelier.inspection.text.types import (
    CorpusMode,
    TextScope,
    TokenMode,
    TokenSettings,
)
from datelier.io.types import ImportFormat, ObjectOptions
from datelier.pipeline.operations import Sort
from datelier.workspace.sessions.jobs import save_snapshot


def test_named_list_corpus_shared_tokenizer_and_stale_selection_scope(
    tmp_path: Path,
) -> None:
    first_path, second_path = tmp_path / "records.json", tmp_path / "other.csv"
    first_path.write_text(
        json.dumps(
            {"rows": [{"body": ["A a", "B"]}, {"body": ["c c c"]}, {"body": []}]}
        )
    )
    second_path.write_text("text\nA\nB B B\n")
    originals = first_path.read_bytes(), second_path.read_bytes()
    editor = EditorController()
    try:
        root = editor.active
        root.open(first_path, ObjectOptions(), format=ImportFormat.OBJECT)
        until(editor, lambda: root.objects.root is not None)
        named = root.record_views.open(root, ("rows",))
        other = editor.new_file(second_path)
        until(
            editor,
            lambda: named.inspection is not None and other.inspection is not None,
        )
        model = editor.compare.text
        model.map_files((named.identity, other.identity))
        assert tuple(s.column for s in model.draft.sources) == ("body", "text")
        for mapping in model.draft.sources:
            model.update_mapping(
                replace(mapping, scope=TextScope(CorpusMode.COLLECTION))
            )
        other.text.jobs.settings = replace(
            other.text.jobs.settings,
            tokens=TokenSettings(TokenMode.WHITESPACE, lowercase=True),
        )
        editor.poll()
        model.copy_tokenizer()
        assert model.draft.tokens == other.text.jobs.settings.tokens
        assert model.active is None and model.jobs.started == 0
        model.prepare()
        until(editor, lambda: model.active is not None)
        result = model.active
        assert result and result.profiles[0].is_list
        assert [p.tokens for p in result.profiles] == [6, 4]
        assert result.frequencies["piece"].to_list() == ["b", "a", "c"]
        assert result.view_names[0] == named.view_name
        assert (
            dict((r[2], r[3]) for r in model.statistics if r[0] == result.labels[0])[
                "Counted tokens"
            ]
            == 6
        )
        model.draft = replace(model.draft, bins=6)
        editor.activate(root.identity)
        editor.poll()
        assert model.active is result and model.changed
        model.select(0, 0)
        assert editor.current is named
        editor.activate(other.identity)
        until(
            editor,
            lambda: "matching source rows selected" in model.jobs.selection_message,
        )
        assert editor.current is other and not root.selection.row_ids
        other.editor.request(Sort(("text",)))
        until(editor, lambda: not other.editor.busy)
        assert model.active is None and model.jobs.started == 1
        assert originals == (first_path.read_bytes(), second_path.read_bytes())
        assert all(
            f.text.corpus.profile is None and not f.text.jobs.settings.tokens.artifact
            for f in editor.all_files
        )
    finally:
        editor.close()


def test_saved_text_view_and_closed_contributor_do_not_implicitly_prepare(
    tmp_path: Path,
) -> None:
    first, second = tmp_path / "a.csv", tmp_path / "b.csv"
    first.write_text("text\na a\nb\n")
    second.write_text("other\nc\nd d\n")
    workspace = tmp_path / "session.json"
    editor = EditorController()
    try:
        a = editor.active
        a.open(first)
        b = editor.new_file(second)
        until(editor, lambda: a.inspection is not None and b.inspection is not None)
        model = editor.compare.text
        model.map_files((a.identity, b.identity))
        model.apply()
        model.view = TextComparisonViewSettings("Token frequencies", 1, 2, True, 335)
        editor.poll()
        assert model.jobs.started == 0
        save_snapshot(workspace, capture_session(editor), False)
    finally:
        editor.close()
    reopened = EditorController()
    try:
        reopened.open_workspace(workspace)
        until(
            reopened, lambda: not reopened.workspace.busy and len(reopened.files) == 2
        )
        model = reopened.compare.text
        assert model.view == TextComparisonViewSettings(
            "Token frequencies", 1, 2, True, 335
        )
        assert len(model.recipes[0].sources) == 2 and model.jobs.started == 0
        model.prepare()
        until(reopened, lambda: model.active is not None)
        reopened.close_file(reopened.files[0].identity)
        reopened.poll()
        assert len(model.recipes[0].sources) == 1 and model.active is None
        assert model.jobs.started == 1
        capture_session(reopened).workspace.validate()
    finally:
        reopened.close()
