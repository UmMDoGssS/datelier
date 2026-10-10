"""Explicit local trainers and source provenance; no implicit Hub operations."""

import hashlib
import json
import os
from collections.abc import Iterator
from dataclasses import asdict, dataclass
from itertools import chain
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Event

import tokenizers
from tokenizers import Tokenizer, models, pre_tokenizers, trainers

from datelier.core.dataset import Dataset
from datelier.inspection.references.index import ReferenceIndex
from datelier.inspection.references.types import ReferenceSettings
from datelier.inspection.text.corpus import (
    TextProgress,
    check_abandoned,
    corpus_documents,
    corpus_positions,
)
from datelier.inspection.text.list_records import is_text_list
from datelier.inspection.text.tokenization import normalization
from datelier.inspection.text.types import (
    TextSettings,
    TextStatus,
    TokenizerReference,
    TokenMode,
)
from datelier.workspace.storage import fingerprint, protect_sources, reference_source


@dataclass(frozen=True)
class TrainedTokenizer:
    reference: TokenizerReference
    requested: int
    documents: int
    nulls: int
    empty: int
    tokenless: int
    input_sha256: str


def remove_unaccepted(result: TrainedTokenizer) -> None:
    """Only this job's newly-created artifact files are eligible for removal."""
    for name, digest in (
        (result.reference.path, result.reference.sha256),
        (result.reference.provenance_path, result.reference.provenance_sha256),
    ):
        if name is not None:
            path = Path(name)
            if (
                path.is_file()
                and hashlib.sha256(path.read_bytes()).hexdigest() == digest
            ):
                path.unlink(missing_ok=True)


def train_tokenizer(
    dataset: Dataset,
    file_id: str,
    settings: TextSettings,
    selection: tuple[int, ...],
    references: ReferenceSettings,
    index: ReferenceIndex | None,
    stop: Event,
    progress: TextProgress,
) -> TrainedTokenizer:
    settings.validate()
    training = settings.training
    if not training.output_path.strip():
        raise ValueError("Choose a new local tokenizer JSON output path")
    output = Path(training.output_path).expanduser().resolve()
    sidecar = output.with_name(output.name + ".provenance.json")
    protect_sources(output, (dataset.source.path,))
    if output.exists() or sidecar.exists():
        raise ValueError(
            "Tokenizer output or provenance already exists; choose a new path"
        )
    source = reference_source(dataset.source)
    positions = corpus_positions(dataset, settings.scope, selection)
    if not len(positions):
        raise ValueError("Training scope contains no records")
    requested_ids: list[int] = []
    element_paths: list[list[int]] = []
    dtype = dataset.table.schema.get(settings.column or "")
    text_list = dtype is not None and is_text_list(dtype)
    digest = hashlib.sha256()
    nulls = empty = tokenless = documents = 0
    configured_normalizer = normalization(settings.tokens)
    pre_tokenizer = pre_tokenizers.Whitespace()

    def texts() -> Iterator[str]:
        nonlocal nulls, empty, tokenless, documents
        for doc in corpus_documents(
            dataset, file_id, settings, positions, references, index, stop, progress
        ):
            requested_ids.append(doc.origin.row_id)
            if text_list:
                element_paths.append(list(doc.origin.element_path))
            content_digest = hashlib.sha256(doc.text.encode("utf8")).hexdigest()
            digest.update(
                json.dumps(
                    [
                        (doc.origin.row_id, doc.origin.element_path)
                        if text_list
                        else doc.origin.row_id,
                        doc.status.value,
                        doc.path,
                        content_digest,
                    ],
                    ensure_ascii=False,
                ).encode("utf8")
            )
            if doc.status == TextStatus.ERROR:
                raise ValueError(f"Source row {doc.origin.row_id}: {doc.diagnostic}")
            if doc.status == TextStatus.NULL:
                nulls += 1
            elif doc.status == TextStatus.EMPTY:
                empty += 1
            elif not pre_tokenizer.pre_tokenize_str(
                configured_normalizer.normalize_str(doc.text)
            ):
                tokenless += 1
            else:
                documents += 1
                yield doc.text
        progress.update(
            "Training tokenizer (native progress unavailable)",
            len(positions),
            len(positions),
        )

    tokenizer = Tokenizer(
        models.BPE(unk_token="[UNK]")
        if training.mode == TokenMode.BPE
        else models.Unigram()
    )
    tokenizer.normalizer = configured_normalizer
    tokenizer.pre_tokenizer = pre_tokenizer
    trainer = (
        trainers.BpeTrainer(
            vocab_size=training.vocabulary_size,
            min_frequency=training.min_frequency,
            special_tokens=list(training.special_tokens),
            show_progress=False,
        )
        if training.mode == TokenMode.BPE
        else trainers.UnigramTrainer(
            vocab_size=training.vocabulary_size,
            special_tokens=list(training.special_tokens),
            unk_token="[UNK]",
            max_piece_length=training.max_piece_length,
            n_sub_iterations=training.iterations,
            shrinking_factor=training.shrinking_factor,
            show_progress=False,
        )
    )
    progress.update(
        "Reading records / training (trainer has no progress API)", 0, len(positions)
    )
    inputs = texts()
    first = next(inputs, None)
    if first is None:
        raise ValueError("Training requires a decoded document with token pieces")
    tokenizer.train_from_iterator(
        chain((first,), inputs),
        trainer=trainer,
        length=None if text_list else len(positions),
    )
    check_abandoned(stop)
    if fingerprint(dataset.source.path) != source:
        raise ValueError("Source changed during training; reopen it and retry")
    if not documents:
        raise ValueError("Training requires a nonempty decoded document")
    payload = tokenizer.to_str(pretty=True).encode("utf8")
    provenance: dict[str, object] = {
        "version": 1,
        "tokenizers_version": tokenizers.__version__,
        "source": asdict(source),
        "file_id": file_id,
        "dataset_revision": str(dataset.revision.token),
        "field": settings.column,
        "text_source": settings.source.value,
        "encoding": settings.encoding,
        "scope": asdict(settings.scope),
        "source_row_ids": requested_ids,
        "normalization": settings.tokens.normalization.value,
        "lowercase": settings.tokens.lowercase,
        "trainer": asdict(training),
        "pre_tokenizer": "Unicode word/punctuation runs",
        "documents": documents,
        "nulls": nulls,
        "empty": empty,
        "tokenless": tokenless,
        "input_sha256": digest.hexdigest(),
        "tokenizer_sha256": hashlib.sha256(payload).hexdigest(),
    }
    if text_list:
        provenance["source_element_paths"] = element_paths
    provenance_payload = (
        json.dumps(provenance, ensure_ascii=False, indent=2) + "\n"
    ).encode("utf8")
    linked: list[Path] = []
    try:
        with TemporaryDirectory(
            prefix=".datelier-train-", dir=output.parent
        ) as temporary:
            staging = Path(temporary)
            for name, data in (
                ("tokenizer", payload),
                ("provenance", provenance_payload),
            ):
                with (staging / name).open("wb") as stream:
                    stream.write(data)
                    stream.flush()
                    os.fsync(stream.fileno())
            check_abandoned(stop)
            # Hard links publish complete files without overwriting any existing
            # destination, including a destination created during training.
            for name, path in (("provenance", sidecar), ("tokenizer", output)):
                os.link(staging / name, path)
                linked.append(path)
                check_abandoned(stop)
    except BaseException:
        for path in linked:
            path.unlink(missing_ok=True)
        raise
    return TrainedTokenizer(
        TokenizerReference(
            str(output),
            hashlib.sha256(payload).hexdigest(),
            training.mode,
            str(sidecar),
            hashlib.sha256(provenance_payload).hexdigest(),
        ),
        len(positions),
        documents,
        nulls,
        empty,
        tokenless,
        digest.hexdigest(),
    )
