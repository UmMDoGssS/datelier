"""Selected-corpus training, provenance, safe publication and abandonment."""

import json
from dataclasses import replace
from pathlib import Path
from threading import Event
from time import monotonic, sleep
from unittest.mock import patch

import polars as pl
import pytest

from datelier.core.jobs import SharedWorkers
from datelier.inspection.references.types import ReferenceSettings
from datelier.inspection.text.corpus import TextProgress, corpus_positions
from datelier.inspection.text.jobs import TextJobs
from datelier.inspection.text.records import read_document
from datelier.inspection.text.tokenization import TextTokenizer, import_tokenizer
from datelier.inspection.text.training import TrainedTokenizer, train_tokenizer
from datelier.inspection.text.types import (
    CorpusMode,
    Normalization,
    TextScope,
    TextSettings,
    TextSource,
    TokenMode,
    TokenSettings,
    TrainingSettings,
)
from datelier.io.importing import load_file
from datelier.workspace.codec import decode_record, encode
from datelier.workspace.types import WorkspaceViews


@pytest.mark.parametrize("mode", [TokenMode.BPE, TokenMode.UNIGRAM])
def test_selected_training_provenance_and_reusable_artifact(
    tmp_path: Path, mode: TokenMode
) -> None:
    source = tmp_path / "corpus.csv"
    pl.DataFrame(
        {
            "id": range(5),
            "text": ["HELLO hello 中 é", "excluded secret", None, "", "   "],
        }
    ).write_csv(source)
    original = source.read_bytes()
    dataset = load_file(source).dataset
    dataset = dataset.with_rows(dataset.table.reverse(), dataset.row_ids.reverse())
    settings = TextSettings(
        "text",
        TextSource.INLINE,
        tokens=TokenSettings(TokenMode.WORD, Normalization.NFC, lowercase=True),
        scope=TextScope(CorpusMode.SELECTION),
        training=TrainingSettings(
            mode,
            vocabulary_size=25,
            min_frequency=1,
            output_path=str(tmp_path / "trained.json"),
        ),
    )
    result = train_tokenizer(
        dataset,
        "view",
        settings,
        (0, 2, 3, 4),
        ReferenceSettings(),
        None,
        Event(),
        TextProgress(),
    )
    assert (
        result.requested,
        result.documents,
        result.nulls,
        result.empty,
        result.tokenless,
    ) == (4, 1, 1, 1, 1)
    assert result.reference.provenance_path
    saved = json.loads(Path(result.reference.provenance_path).read_text())
    assert saved["source_row_ids"] == [4, 3, 2, 0]
    assert saved["file_id"] == "view" and saved["source"]["path"] == str(source)
    assert saved["trainer"]["mode"] == mode.value
    assert saved["normalization"] == "NFC" and saved["lowercase"]
    assert saved["input_sha256"] == result.input_sha256
    reference = import_tokenizer(Path(result.reference.path))
    assert reference == result.reference
    tokens = replace(settings.tokens, mode=mode, artifact=reference)
    doc = read_document(dataset, "view", "text", 4, source=TextSource.INLINE)
    assert TextTokenizer(tokens).encode(doc) == TextTokenizer(tokens).encode(doc)
    assert all(
        "secret" not in t.piece for t in TextTokenizer(tokens).encode(doc).tokens
    )
    recipe = WorkspaceViews(text=replace(settings, tokens=tokens))
    assert decode_record(WorkspaceViews, encode(recipe)) == recipe
    assert source.read_bytes() == original
    sidecar = Path(reference.provenance_path or "")
    sidecar.write_text(sidecar.read_text() + "\n")
    with pytest.raises(ValueError, match="provenance changed"):
        TextTokenizer(tokens)
    sidecar.unlink()
    with pytest.raises(OSError):
        TextTokenizer(tokens)


def test_scopes_track_current_rows_and_seed_source_identity(tmp_path: Path) -> None:
    source = tmp_path / "scope.csv"
    pl.DataFrame({"text": [f"text {i}" for i in range(10)]}).write_csv(source)
    dataset = load_file(source).dataset
    dataset = dataset.with_rows(
        dataset.table.reverse().head(6), dataset.row_ids.reverse().head(6)
    )
    assert dataset.row_ids.gather(
        corpus_positions(dataset, TextScope(CorpusMode.RANGE, 2, 2), ())
    ).to_list() == [8, 7]
    assert dataset.row_ids.gather(
        corpus_positions(dataset, TextScope(CorpusMode.SELECTION), (0, 8))
    ).to_list() == [8]
    assert len(corpus_positions(dataset, TextScope(CorpusMode.COLLECTION), ())) == 6
    scope = TextScope(CorpusMode.RANDOM, count=3, seed=17)
    assert (
        corpus_positions(dataset, scope, ()).to_list()
        == corpus_positions(dataset, scope, ()).to_list()
    )


@pytest.mark.parametrize("mode", [TokenMode.BPE, TokenMode.UNIGRAM])
def test_empty_and_failed_reads_do_not_publish(tmp_path: Path, mode: TokenMode) -> None:
    source = tmp_path / "empty.csv"
    pl.DataFrame({"text": [None, "", "  "]}, schema={"text": pl.String}).write_csv(
        source
    )
    dataset = load_file(source).dataset
    output = tmp_path / "trained.json"
    settings = TextSettings(
        "text",
        TextSource.INLINE,
        training=TrainingSettings(mode, output_path=str(output)),
    )
    with pytest.raises(ValueError, match="token pieces"):
        train_tokenizer(
            dataset,
            "file",
            settings,
            (),
            ReferenceSettings(),
            None,
            Event(),
            TextProgress(),
        )
    assert not output.exists() and not list(tmp_path.glob(".datelier-train-*"))
    broken = tmp_path / "bad.txt"
    broken.write_bytes(b"\xff")
    pl.DataFrame({"text": [str(broken)]}).write_csv(source)
    dataset = load_file(source).dataset
    with pytest.raises(Exception, match="Cannot decode text"):
        train_tokenizer(
            dataset,
            "file",
            replace(settings, source=TextSource.EXTERNAL),
            (),
            ReferenceSettings(),
            None,
            Event(),
            TextProgress(),
        )
    assert not output.exists()


def test_failed_publish_preserves_existing_destination_and_source(
    tmp_path: Path,
) -> None:
    source = tmp_path / "corpus.csv"
    source.write_text("text\nhello hello world\n")
    dataset = load_file(source).dataset
    output = tmp_path / "tokenizer.json"
    settings = TextSettings(
        "text", TextSource.INLINE, training=TrainingSettings(output_path=str(output))
    )
    import os

    original_link = os.link

    def collision(src: Path, dst: Path) -> None:
        if dst == output:
            output.write_text("user content created during training")
        original_link(src, dst)

    with (
        patch("datelier.inspection.text.training.os.link", side_effect=collision),
        pytest.raises(FileExistsError),
    ):
        train_tokenizer(
            dataset,
            "file",
            settings,
            (),
            ReferenceSettings(),
            None,
            Event(),
            TextProgress(),
        )
    assert output.read_text() == "user content created during training"
    assert not Path(str(output) + ".provenance.json").exists()
    assert not list(tmp_path.glob(".datelier-train-*"))
    with pytest.raises(ValueError, match="overwrite source"):
        train_tokenizer(
            dataset,
            "file",
            replace(
                settings, training=replace(settings.training, output_path=str(source))
            ),
            (),
            ReferenceSettings(),
            None,
            Event(),
            TextProgress(),
        )


def test_running_and_completed_unaccepted_training_are_retired(tmp_path: Path) -> None:
    source = tmp_path / "corpus.csv"
    source.write_text("text\nhello hello world\n")
    dataset = load_file(source).dataset
    started, release = Event(), Event()
    workers = SharedWorkers()
    jobs = TextJobs(workers)
    output = tmp_path / "tokenizer.json"
    settings = TextSettings(
        "text", TextSource.INLINE, training=TrainingSettings(output_path=str(output))
    )
    jobs.settings = settings
    jobs.bind(dataset, "file", ReferenceSettings(), None)
    original_train = train_tokenizer

    def slow(*args: object) -> TrainedTokenizer:
        started.set()
        assert release.wait(3)
        return original_train(
            dataset,
            "file",
            settings,
            (),
            ReferenceSettings(),
            None,
            jobs._stop,
            TextProgress(),
        )

    try:
        assert not jobs.busy
        with patch("datelier.inspection.text.jobs.train_tokenizer", side_effect=slow):
            jobs.request_training()
        assert started.wait(3)
        running = jobs._training
        assert running is not None
        jobs.abandon()
        release.set()
        with pytest.raises(ValueError, match="abandoned"):
            running.result(3)
        assert jobs.settings == settings and not output.exists()
        jobs.request_training()
        completed = jobs._training
        assert completed is not None
        completed.result(3)
        assert output.exists()
        jobs.close()  # Completed but never accepted into settings.
        workers.shutdown()
        assert (
            not output.exists() and not Path(str(output) + ".provenance.json").exists()
        )
        jobs.poll()
        assert jobs.settings == settings
    finally:
        release.set()
        jobs.close()
        workers.shutdown()


def test_training_command_accepts_only_success_and_never_runs_on_bind(
    tmp_path: Path,
) -> None:
    source = tmp_path / "corpus.csv"
    source.write_text("text\nhello hello world\n")
    dataset = load_file(source).dataset
    jobs = TextJobs()
    try:
        settings = TextSettings(
            "text",
            TextSource.INLINE,
            training=TrainingSettings(output_path=str(tmp_path / "tokenizer.json")),
        )
        jobs.settings = settings
        jobs.bind(dataset, "file", ReferenceSettings(), None)
        jobs.poll()
        assert not jobs.busy and not list(tmp_path.glob("*.json"))
        jobs.request_training()
        deadline = monotonic() + 5
        while jobs.busy and monotonic() < deadline:
            jobs.poll()
            sleep(0.001)
        assert jobs.settings.tokens.artifact and "Trained BPE" in jobs.message
        accepted = jobs.settings
        jobs.bind(dataset, "file", ReferenceSettings(), None)
        jobs.request_training()  # Destination already exists.
        deadline = monotonic() + 5
        while jobs.busy and monotonic() < deadline:
            jobs.poll()
            sleep(0.001)
        assert jobs.settings == accepted and "Training failed" in jobs.message
    finally:
        jobs.close()
