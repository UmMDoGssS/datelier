"""Explicit commands, settings/revision invalidation and saved text recipes."""

from concurrent.futures import Future
from dataclasses import replace
from pathlib import Path
from threading import Event
from time import monotonic, sleep
from unittest.mock import patch

import polars as pl
from tokenizers import Tokenizer, models

from datelier.application.editor import EditorController
from datelier.core.dataset import Dataset, SourceReference
from datelier.core.jobs import SharedWorkers
from datelier.inspection.references.types import ReferenceSettings
from datelier.inspection.text.jobs import TextJobs, prepare_document
from datelier.inspection.text.types import (
    Normalization,
    TextSettings,
    TextSource,
    TokenizedDocument,
    TokenMode,
    TokenSettings,
)
from datelier.workspace.codec import decode_record, encode
from datelier.workspace.types import WorkspaceViews


def wait(jobs: TextJobs) -> None:
    deadline = monotonic() + 5
    while jobs.busy and monotonic() < deadline:
        jobs.poll()
        sleep(0.001)
    assert not jobs.busy, jobs.message


def test_commands_and_failed_import_keep_prior_recipe(tmp_path: Path) -> None:
    dataset = Dataset.from_source(
        pl.DataFrame({"text": ["hello 中"]}), SourceReference(tmp_path / "data", 0, 0)
    )
    jobs = TextJobs()
    try:
        jobs.settings = TextSettings("text", TextSource.INLINE)
        jobs.bind(dataset, "first", ReferenceSettings(), None)
        assert not jobs.busy and jobs.active is None
        jobs.request_document()
        wait(jobs)
        assert jobs.active and jobs.active.count == 2
        assert jobs.active.document.origin.file_id == "first"
        before = jobs.settings
        jobs.request_import(tmp_path / "missing.json")
        wait(jobs)
        assert "Cannot load tokenizer" in jobs.message and jobs.settings == before
        path = tmp_path / "bpe.json"
        Tokenizer(models.BPE({"中": 0}, [])).save(str(path))
        jobs.request_import(path)
        wait(jobs)
        assert jobs.settings.tokens.mode == TokenMode.BPE
        jobs.bind(dataset, "first", ReferenceSettings(), None)
        jobs.request_document()
        wait(jobs)
        assert jobs.active
        path.write_text(path.read_text() + "\n")
        jobs.request_document()
        wait(jobs)
        assert "changed" in jobs.message and jobs.active is None
        jobs.request_import(path)
        wait(jobs)
        jobs.bind(dataset, "first", ReferenceSettings(), None)
        jobs.request_document()
        wait(jobs)
        assert jobs.active
    finally:
        jobs.close()


def test_obsolete_or_closed_work_cannot_publish(tmp_path: Path) -> None:
    dataset = Dataset.from_source(
        pl.DataFrame({"text": ["hello 中"]}), SourceReference(tmp_path / "data", 0, 0)
    )
    workers = SharedWorkers()
    first, second = TextJobs(workers), TextJobs(workers)
    started, release = Event(), Event()

    def slow(*args: object) -> TokenizedDocument:
        started.set()
        assert release.wait(3)
        return prepare_document(
            dataset, "first", first.settings, ReferenceSettings(), None
        )

    try:
        for identity, jobs in (("first", first), ("second", second)):
            jobs.settings = TextSettings("text", TextSource.INLINE)
            jobs.bind(dataset, identity, ReferenceSettings(), None)
        with patch("datelier.inspection.text.jobs.prepare_document", side_effect=slow):
            first.request_document()
        assert started.wait(3)
        running: Future[TokenizedDocument] | None = first._document
        assert running is not None
        first.settings = replace(
            first.settings, tokens=TokenSettings(TokenMode.CHARACTER)
        )
        first.bind(dataset, "first", ReferenceSettings(), None)
        assert first.active is None and not first.busy
        first.close()
        second.request_document()
        wait(second)
        release.set()
        running.result(3)
        first.poll()
        assert first.active is None
        assert second.active and second.active.document.origin.file_id == "second"
        second.bind(
            dataset.with_role("text", None), "second", ReferenceSettings(), None
        )
        assert second.active is None
    finally:
        release.set()
        first.close()
        second.close()
        workers.shutdown()


def test_saved_configuration_and_legacy_defaults_restore_without_work(
    tmp_path: Path,
) -> None:
    from datelier.application.workspace import capture_views

    path = tmp_path / "source.csv"
    path.write_text("id,text\n1,Hello world\n2,你好\n")
    editor = EditorController()
    try:
        file = editor.new_file(path)
        deadline = monotonic() + 5
        while not file.loader.active and monotonic() < deadline:
            editor.poll()
            sleep(0.001)
        assert file.loader.active
        file.text.jobs.settings = TextSettings(
            "text",
            TextSource.INLINE,
            "utf-8-sig",
            TokenSettings(TokenMode.CHARACTER, Normalization.NFC, lowercase=True),
            1,
        )
        saved = capture_views(file)
        assert decode_record(WorkspaceViews, encode(saved)) == saved
        legacy = encode(saved)
        assert isinstance(legacy, dict)
        legacy.pop("text")
        assert decode_record(WorkspaceViews, legacy).text == TextSettings()
        workspace = tmp_path / "session.datelier.json"
        editor.save_workspace(workspace, "", (), False, True)
        deadline = monotonic() + 5
        while editor.workspace.session_busy and monotonic() < deadline:
            editor.poll()
            sleep(0.001)
        assert editor.workspace.saved
        editor.open_workspace(workspace)
        deadline = monotonic() + 5
        while editor.workspace.session_busy and monotonic() < deadline:
            editor.poll()
            sleep(0.001)
        reopened = next(f for f in editor.files if f.loader.active)
        assert reopened.text.jobs.settings == saved.text
        assert reopened.text.jobs.active is None and not reopened.text.jobs.busy
    finally:
        editor.close()
