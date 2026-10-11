"""Corpus/record job independence and explicit training publication in the rebuild."""

import json
from collections.abc import Callable
from dataclasses import replace
from pathlib import Path
from time import monotonic, sleep

import polars as pl

from datelier.application.exploration import ProfileFamily
from datelier.application.sessions import EditorController
from datelier.inspection.text.types import (
    CorpusMode,
    TextScope,
    TokenMode,
    TrainingSettings,
)


def until(editor: EditorController, condition: Callable[[], bool]) -> None:
    deadline = monotonic() + 5
    while monotonic() < deadline:
        editor.poll()
        if condition():
            return
        sleep(0.001)
    raise AssertionError("Text work timed out")


def test_corpus_and_record_results_remain_independent(tmp_path: Path) -> None:
    path = tmp_path / "corpus.csv"
    pl.DataFrame(
        {"body": ["a a b", "b c", "", None, "a"], "other": ["different"] * 5}
    ).write_csv(path)
    original = path.read_bytes()
    editor = EditorController()
    try:
        file = editor.active
        file.open(path)
        until(editor, lambda: file.inspection is not None)
        file.profiles.choose(("body",))
        file.profiles.text = True
        file.text.jobs.settings = replace(
            file.text.jobs.settings, scope=TextScope(CorpusMode.COLLECTION)
        )
        editor.poll()
        assert file.profiles.family == ProfileFamily.TEXT
        assert file.text.corpus.profile is None and not file.text.corpus.busy
        file.text.request_profile("body")
        until(editor, lambda: file.text.corpus.profile is not None)
        corpus = file.text.corpus.profile
        assert corpus and corpus.profile.tokens == 6 and corpus.profile.documents == 4
        assert corpus.profile.nulls == 1 and corpus.profile.empty == 1
        assert dict(file.text.statistics)["Counted tokens"] == 6
        assert dict(file.text.statistics)["Null"] == 1
        file.text.request_record("other", 2)
        until(editor, lambda: file.text.jobs.active is not None)
        assert file.text.corpus.profile is corpus
        assert (
            file.text.jobs.active and file.text.jobs.active.document.text == "different"
        )
        assert file.text.jobs.active.document.origin.row_id == 2
        assert path.read_bytes() == original
    finally:
        editor.close()


def test_training_publishes_shared_recipe_with_explicit_selected_provenance(
    tmp_path: Path,
) -> None:
    path, output = tmp_path / "corpus.csv", tmp_path / "tokenizer.json"
    path.write_text('body\n"hello hello 中"\n"excluded secret"\n')
    original = path.read_bytes()
    editor = EditorController()
    try:
        file = editor.active
        file.open(path)
        until(editor, lambda: file.inspection is not None)
        assert file.inspection
        file.selection.choose(file.inspection.dataset.revision, (0,))
        file.text.jobs.settings = replace(
            file.text.jobs.settings,
            scope=TextScope(CorpusMode.SELECTION),
            training=TrainingSettings(
                TokenMode.BPE,
                vocabulary_size=32,
                min_frequency=1,
                output_path=str(output),
            ),
        )
        editor.choose_route("Correlations")
        editor.poll()
        file.text.request_training("body")
        until(editor, lambda: file.text.jobs.settings.tokens.artifact is not None)
        assert file.views.tab == "Correlations"
        artifact = file.text.jobs.settings.tokens.artifact
        assert artifact and artifact.mode == TokenMode.BPE and artifact.provenance_path
        provenance = json.loads(Path(artifact.provenance_path).read_text())
        assert provenance["source_row_ids"] == [0]
        assert file.text.jobs.active is None
        assert path.read_bytes() == original
    finally:
        editor.close()


def test_saved_text_subview_and_tokenizer_reopen_without_work(tmp_path: Path) -> None:
    from datelier.application.sessions.workspace import capture_session
    from datelier.workspace.sessions.jobs import save_snapshot

    source, workspace = tmp_path / "source.csv", tmp_path / "session.json"
    source.write_text('body\n"é 中"\n')
    editor = EditorController()
    try:
        file = editor.active
        file.open(source)
        until(editor, lambda: file.inspection is not None)
        file.text.profile_tab = "Token frequencies"
        file.text.jobs.settings = replace(
            file.text.jobs.settings,
            tokens=replace(file.text.jobs.settings.tokens, mode=TokenMode.CHARACTER),
            scope=TextScope(CorpusMode.COLLECTION),
        )
        file.profiles.choose(())
        editor.poll()
        assert file.profiles.selected == ()
        save_snapshot(workspace, capture_session(editor), False)
    finally:
        editor.close()
    reopened = EditorController()
    try:
        reopened.open_workspace(workspace)
        until(reopened, lambda: not reopened.workspace.busy)
        file = reopened.active
        assert file.text.profile_tab == "Token frequencies"
        assert file.text.jobs.settings.tokens.mode == TokenMode.CHARACTER
        assert file.profiles.selected == ()
        assert file.text.corpus.profile is None and not file.text.corpus.busy
        assert file.text.jobs.active is None and not file.text.jobs.busy
    finally:
        reopened.close()
